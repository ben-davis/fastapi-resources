from typing import Callable, List, Literal, Optional, Type, TypeVar, Union

from fastapi import HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import create_model
from pydantic.main import BaseModel, ModelMetaclass

from fastapi_resources.resources.types import (
    Inclusions,
    RelationshipInfo,
    Relationships,
    ResourceProtocol,
)
from fastapi_resources.routers import base_router

from . import types

include_query = Query(None, regex=r"^([\w\.]+)(,[\w\.]+)*$")


TResource = TypeVar("TResource", bound=ResourceProtocol)


def get_schemas_from_relationships(
    relationships: Relationships, visited: Optional[set[type[types.Object]]] = None
) -> list[tuple[str, ModelMetaclass]]:
    schemas: list[tuple[str, ModelMetaclass]] = []

    visited = visited or set()
    for relationship_info in relationships.values():
        schema = relationship_info.schema_with_relationships.schema
        if schema in visited:
            continue

        visited.add(schema)
        schemas.append((relationship_info.field, schema))
        schemas += get_schemas_from_relationships(
            relationships=relationship_info.schema_with_relationships.relationships,
            visited=visited,
        )

    return schemas


def get_relationships_model_for_model(
    method: str, resource_class: type[TResource], model: type[BaseModel]
):
    allowed_fields = set(model.__fields__.keys())
    allowed_fields.update(model.__sqlmodel_relationships__.keys())

    RelationshipLinkages = {
        relationship_name: (
            Optional[
                create_model(
                    f"{model.__name__}__{method}__Relationships{relationship_name}",
                    __base__=(
                        (
                            types.JARelationshipsObjectMany
                            if relationship_info.many
                            else types.JARelationshipsObjectSingle
                        )
                    )[
                        Literal[
                            resource_class.registry[
                                relationship_info.schema_with_relationships.schema
                            ].name  # type: ignore
                        ]
                    ],
                )
            ],
            None,
        )
        for relationship_name, relationship_info in resource_class.get_relationships().items()
        if relationship_info.schema_with_relationships.schema in resource_class.registry
        and relationship_info.field in allowed_fields
    }

    Relationships = create_model(
        f"{model.__name__}__{method}__Relationships",
        **RelationshipLinkages,
        __base__=BaseModel,
    )

    return Relationships


def get_attributes_model_for_model(
    method: str, model: type[BaseModel], resource_class: type[TResource]
):
    Attributes = create_model(f"{model.__name__}__{method}__Attributes", __base__=model)

    # Remove the ID
    if "id" in Attributes.__fields__:
        del Attributes.__fields__["id"]

    return Attributes


def get_model_for_resource_class(
    method: str, model: type[BaseModel], resource_class: type[TResource]
):
    Attributes = get_attributes_model_for_model(
        method=method, model=model, resource_class=resource_class
    )
    Relationships = get_relationships_model_for_model(
        method=method, model=model, resource_class=resource_class
    )

    return types.JAResourceObject[
        Attributes,
        Relationships,
        Literal[(resource_class.name,)],  # type: ignore
    ]


def parse_exception(exception: Exception | RequestValidationError):
    print("HEYU", exception)
    if isinstance(exception, RequestValidationError):
        errors = [
            {
                "status": 422,
                "code": error["type"],
                "title": error["msg"],
                "source": f'/{"/".join(str(l) for l in error["loc"])}',
            }
            for error in exception.errors()
        ]
    elif isinstance(exception, HTTPException):
        print("HEY")
        errors = [
            {
                "status": exception.status_code,
                "code": exception.detail,
                "title": exception.detail,
            }
        ]
    else:
        errors = [
            {
                "status": 500,
                "code": "unknown_error",
                "title": "An unknown error occured",
            }
        ]

    return {"errors": errors}


class JSONAPIResourceRoute(base_router.ResourceRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                response: Response = await original_route_handler(request)
            except (HTTPException, RequestValidationError) as exc:
                response = JSONResponse(
                    status_code=getattr(exc, "status_code", 422),
                    content=parse_exception(exc),
                )

            if resource := getattr(request, "resource", None):
                resource.close()

            return response

        return custom_route_handler


class JSONAPIResourceRouter(base_router.ResourceRouter[TResource]):
    route_class = JSONAPIResourceRoute

    def __init__(
        self,
        *,
        resource_class: type[TResource],
        **kwargs,
    ) -> None:
        self.resource_class = resource_class

        super().__init__(
            resource_class=resource_class,
            prefix=f"/{resource_class.plural_name}",
            **kwargs,
        )

    def get_included_schema(
        self, method: str
    ) -> tuple[type[types.JAResourceObject], ...]:
        relationships = self.resource_class.get_relationships()
        schemas = get_schemas_from_relationships(relationships=relationships)

        return tuple(
            get_model_for_resource_class(
                method=f"{self.prefix}__{method}__included__{field}__{schema.__name__}",
                resource_class=self.resource_class.registry[schema],
                model=self.resource_class.registry[schema].Read,
            )
            for field, schema in schemas
            if schema in self.resource_class.registry
        )

    def get_read_response_model(self):
        included_schemas = self.get_included_schema(method="retrieve")
        Included = List[Union[included_schemas]] if included_schemas else list  # type: ignore
        Name = Literal[(self.resource_class.name,)]  # type: ignore

        Attributes = get_attributes_model_for_model(
            method="retrieve",
            model=self.resource_class.Read,
            resource_class=self.resource_class,
        )
        Relationships = get_relationships_model_for_model(
            method="retrieve",
            model=self.resource_class.Read,
            resource_class=self.resource_class,
        )

        return types.JAResponseSingle[Attributes, Relationships, Name, Included]

    def get_list_response_model(self):
        included_schemas = self.get_included_schema(method="list")
        Included = List[Union[included_schemas]] if included_schemas else list  # type: ignore
        Name = Literal[(self.resource_class.name,)]  # type: ignore

        Attributes = get_attributes_model_for_model(
            method="list",
            model=self.resource_class.Read,
            resource_class=self.resource_class,
        )
        Relationships = get_relationships_model_for_model(
            method="list",
            model=self.resource_class.Read,
            resource_class=self.resource_class,
        )

        return types.JAResponseList[Attributes, Relationships, Name, Included]

    def get_update_model(self):
        if not self.resource_class.Update:
            return None

        Name = Literal[(self.resource_class.name,)]  # type: ignore

        Attributes = get_attributes_model_for_model(
            method="update",
            model=self.resource_class.Update,
            resource_class=self.resource_class,
        )
        Relationships = get_relationships_model_for_model(
            method="update",
            model=self.resource_class.Update,
            resource_class=self.resource_class,
        )

        return types.JAUpdateRequest[Attributes, Relationships, Name]

    def get_create_model(self):
        if not self.resource_class.Create:
            return None

        Name = Literal[(self.resource_class.name,)]  # type: ignore

        Attributes = get_attributes_model_for_model(
            method="create",
            model=self.resource_class.Create,
            resource_class=self.resource_class,
        )
        Relationships = get_relationships_model_for_model(
            method="create",
            model=self.resource_class.Create,
            resource_class=self.resource_class,
        )

        return types.JACreateRequest[Attributes, Relationships, Name]

    def get_resource_kwargs(self, request: Request):
        inclusions: Inclusions = []
        include = request.query_params.get("include")

        if include:
            inclusions = [inclusion.split(".") for inclusion in include.split(",")]

        for relationship in self.resource_class.get_relationships().values():
            inclusions.append([relationship.field])

        return {
            **super().get_resource_kwargs(request=request),
            "inclusions": inclusions,
        }

    def build_document_links(self, request: Request):
        path = request.url.path

        if query := request.url.query:
            path = f"{path}?{query}"

        return types.JALinks(self=path)

    def build_resource_object_links(
        self, id: str, resource: Union[Type[TResource], TResource]
    ):
        return types.JALinks(self=f"/{resource.plural_name}/{id}")

    def build_resource_identifier_object(
        self,
        related_obj: types.Object,
        resource: Union[Type[TResource], TResource],
        relationship_info: RelationshipInfo,
    ) -> types.JAResourceIdentifierObject:
        return types.JAResourceIdentifierObject(
            type=resource.registry[
                relationship_info.schema_with_relationships.schema
            ].name,
            id=str(related_obj.id),
        )

    def build_resource_object_relationships(
        self, obj: types.Object, resource: TResource
    ):
        relationships = {}

        for (
            relationship_name,
            relationship_info,
        ) in resource.get_relationships().items():
            links = types.JALinks(
                self=f"/{resource.plural_name}/{obj.id}/relationships/{relationship_name}",
                related=f"/{resource.plural_name}/{obj.id}/{relationship_name}",
            )

            # The relationships will have been properly selected, so this should not send
            # another query.
            data = [
                self.build_resource_identifier_object(
                    related_obj=related_obj.obj,
                    resource=resource,
                    relationship_info=relationship_info,
                )
                for related_obj in resource.get_related(obj, [relationship_name])
                if related_obj.obj
            ]

            if relationship_info.many:
                relationship_object = types.JARelationshipsObjectMany(
                    links=links,
                    data=data,
                )
            else:
                data = data[0] if data else None
                relationship_object = types.JARelationshipsObjectSingle(
                    links=links,
                    data=data,
                )

            relationships[relationship_name] = relationship_object

        # If the relationship is to-one, then we can include `data`
        # But for to-many, we only include it if it's in inclusions.
        return relationships

    def build_resource_object(self, obj: types.Object, resource: TResource):
        valid_attributes = resource.get_attributes()

        # ID is a special case, so can ignored
        valid_attributes.remove("id")

        # Filter out relationships attributes
        attributes = {
            key: value
            for key, value in resource.Read.from_orm(obj).dict().items()
            if key in valid_attributes
        }

        resource_object = types.JAResourceObject(
            id=str(obj.id),
            type=resource.name,
            attributes=attributes,
            links=self.build_resource_object_links(id=obj.id, resource=resource),
            relationships=self.build_resource_object_relationships(
                obj=obj, resource=resource
            ),
        )

        return resource_object

    def build_response(
        self,
        rows: Union[types.Object, list[types.Object]],
        resource: TResource,
        request: Request,
    ):
        included_resources = {}

        many = isinstance(rows, list)
        rows = rows if isinstance(rows, list) else [rows]

        include = request.query_params.get("include")
        inclusions = []

        if include:
            inclusions = [inclusion.split(".") for inclusion in include.split(",")]

        for row in rows:
            for inclusion in inclusions:
                selected_objs = resource.get_related(obj=row, inclusion=inclusion)

                for selected_obj in selected_objs:
                    obj = selected_obj.obj
                    related_resource = selected_obj.resource

                    included_resources[
                        (related_resource.name, obj.id)
                    ] = self.build_resource_object(obj=obj, resource=related_resource())

        data = [self.build_resource_object(obj=row, resource=resource) for row in rows]
        included = list(included_resources.values())

        # Get top-level resource links
        links = self.build_document_links(request=request)

        if many:
            return types.JAResponseList(data=data, included=included, links=links)

        return types.JAResponseSingle(data=data[0], included=included, links=links)

    def _parse_request_payload(self, payload: dict):
        # Merge the attributes and relationships into a single update
        parsed_relationships = {}

        for key, linkage in payload["data"].get("relationships", {}).items():
            identifiers = linkage["data"]
            if isinstance(identifiers, list):
                parsed_relationships[key] = [ro["id"] for ro in identifiers]
            else:
                parsed_relationships[key] = identifiers["id"]

        merged_payload = {
            **payload["data"].get("attributes", {}),
            **parsed_relationships,
        }

        return merged_payload

    def parse_update(self, resource: TResource, update: dict):
        return super().parse_update(
            resource, self._parse_request_payload(payload=update)
        )

    def parse_create(self, resource: TResource, create: dict):
        return super().parse_update(
            resource, self._parse_request_payload(payload=create)
        )

    async def _retrieve(
        self,
        *,
        id: Union[int, str],
        request: Request,
        include: Optional[str] = include_query,
    ):
        return await super()._retrieve(id=id, request=request)

    async def _list(self, *, request: Request, include: Optional[str] = include_query):
        return await super()._list(request=request)

    async def _create(
        self,
        *,
        create: base_router.TCreatePayload,
        request: Request,
        include: Optional[str] = include_query,
    ):
        return await super()._create(create=create, request=request)

    async def _update(
        self,
        *,
        id: Union[int, str],
        update: base_router.TUpdatePayload,
        request: Request,
        include: Optional[str] = include_query,
    ):
        return await super()._update(id=id, update=update, request=request)

    async def _delete(self, *, id: Union[int, str], request: Request):
        return await super()._delete(id=id, request=request)

from typing import Generic, List, Literal, Optional, Type, TypeVar, Union

from fastapi import Query, Request
from fastapi_resources.resources.base_resource import (
    Object,
    Relationships,
    Resource,
    SQLModelRelationshipInfo,
)
from fastapi_resources.resources.types import Inclusions
from fastapi_resources.routers import base_router
from pydantic import create_model
from pydantic.generics import GenericModel
from pydantic.main import BaseModel, ModelMetaclass
from sqlalchemy.orm import MANYTOONE

from .base_router import ResourceRouter

TRead = TypeVar("TRead", bound=Object)
TName = TypeVar("TName", bound=str)
TUpdate = TypeVar("TUpdate", bound=Object)
TCreate = TypeVar("TCreate", bound=Object)
TAttributes = TypeVar("TAttributes")
TRelationships = TypeVar("TRelationships")
TIncluded = TypeVar("TIncluded")
TType = TypeVar("TType")


class TIncludeParam(str):
    pass


class JALinks(BaseModel):
    """A links-object"""

    self: Optional[str]
    # Will be used when relationship endpoints are implemented
    related: Optional[str]


class JAResourceIdentifierObject(GenericModel, Generic[TType]):
    type: TType
    id: str


class JARelationshipsObjectSingle(GenericModel, Generic[TType]):
    links: Optional[JALinks]
    data: Optional[JAResourceIdentifierObject[TType]]


class JARelationshipsObjectMany(GenericModel, Generic[TType]):
    links: Optional[JALinks]
    data: list[JAResourceIdentifierObject[TType]]


class JAResourceObject(GenericModel, Generic[TAttributes, TRelationships, TName]):
    id: str
    type: TName
    attributes: TAttributes
    links: JALinks
    relationships: TRelationships


class JAUpdateObject(GenericModel, Generic[TAttributes, TRelationships, TName]):
    id: str
    type: TName
    attributes: Optional[TAttributes]
    relationships: Optional[TRelationships]


class JAUpdateRequest(GenericModel, Generic[TAttributes, TRelationships, TName]):
    data: JAUpdateObject[TAttributes, TRelationships, TName]


class JACreateObject(GenericModel, Generic[TAttributes, TRelationships, TName]):
    type: TName
    attributes: Optional[TAttributes]
    relationships: Optional[TRelationships]


class JACreateRequest(GenericModel, Generic[TAttributes, TRelationships, TName]):
    data: JACreateObject[TAttributes, TRelationships, TName]


class JAResponseSingle(
    GenericModel, Generic[TAttributes, TRelationships, TName, TIncluded]
):
    data: JAResourceObject[TAttributes, TRelationships, TName]
    included: TIncluded
    links: JALinks


class JAResponseList(
    GenericModel, Generic[TAttributes, TRelationships, TName, TIncluded]
):
    data: List[JAResourceObject[TAttributes, TRelationships, TName]]
    included: TIncluded
    links: JALinks


include_query = Query(None, regex=r"^([\w\.]+)(,[\w\.]+)*$")


def get_schemas_from_relationships(
    relationships: Relationships, visited: Optional[set[type[Object]]] = None
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


def get_relationships_schema_for_resource_class(
    method: str, resource_class: type[Resource]
):
    Read = resource_class.Read

    RelationshipLinkages = {
        relationship_name: (
            Optional[
                create_model(
                    f"{Read.__name__}__{method}__Relationships{relationship_name}",
                    __base__=(
                        (
                            JARelationshipsObjectMany
                            if relationship_info.many
                            else JARelationshipsObjectSingle,
                            Generic[TType],
                        )
                    ),
                )[
                    Literal[
                        resource_class.registry[
                            relationship_info.schema_with_relationships.schema
                        ].name
                    ]
                ]
            ],
            None,
        )
        for relationship_name, relationship_info in resource_class.get_relationships().items()
    }

    Relationships = create_model(
        f"{Read.__name__}__{method}__Relationships",
        **RelationshipLinkages,
        __base__=BaseModel,
    )

    return Relationships


def get_attributes_model_for_resource_class(
    method: str, resource_class: type[Resource]
):
    Read = resource_class.Read
    Attributes = create_model(f"{Read.__name__}__{method}__Attributes", __base__=Read)

    # Remove the ID
    del Attributes.__fields__["id"]

    return Attributes


def get_model_for_resource_class(method: str, resource_class: type[Resource]):
    Attributes = get_attributes_model_for_resource_class(
        method=method, resource_class=resource_class
    )
    Relationships = get_relationships_schema_for_resource_class(
        method=method, resource_class=resource_class
    )

    return JAResourceObject[
        Attributes,
        Relationships,
        Literal[(resource_class.name,)],  # type: ignore
    ]


class JSONAPIResourceRouter(ResourceRouter):
    def __init__(
        self,
        *,
        resource_class: type[Resource],
        **kwargs,
    ) -> None:
        self.resource_class = resource_class

        super().__init__(
            resource_class=resource_class,
            prefix=f"/{resource_class.plural_name}",
            **kwargs,
        )

    def get_included_schema(self, method: str) -> tuple[type[JAResourceObject], ...]:
        relationships = self.resource_class.get_relationships()
        schemas = get_schemas_from_relationships(relationships=relationships)

        return tuple(
            get_model_for_resource_class(
                method=f"{self.prefix}__{method}__included__{field}__{schema.__name__}",
                resource_class=self.resource_class.registry[schema],
            )
            for field, schema in schemas
        )

    def get_read_response_model(self):
        included_schemas = self.get_included_schema(method="retrieve")
        Included = List[Union[included_schemas]] if included_schemas else list  # type: ignore
        Name = Literal[(self.resource_class.name,)]  # type: ignore

        Attributes = get_attributes_model_for_resource_class(
            method="retrieve", resource_class=self.resource_class
        )
        Relationships = get_relationships_schema_for_resource_class(
            method="retrieve", resource_class=self.resource_class
        )

        return JAResponseSingle[Attributes, Relationships, Name, Included]

    def get_list_response_model(self):
        included_schemas = self.get_included_schema(method="list")
        Included = List[Union[included_schemas]] if included_schemas else list  # type: ignore
        Name = Literal[(self.resource_class.name,)]  # type: ignore

        Attributes = get_attributes_model_for_resource_class(
            method="list", resource_class=self.resource_class
        )
        Relationships = get_relationships_schema_for_resource_class(
            method="list", resource_class=self.resource_class
        )

        return JAResponseList[Attributes, Relationships, Name, Included]

    def get_update_model(self):
        Name = Literal[(self.resource_class.name,)]  # type: ignore

        Attributes = get_attributes_model_for_resource_class(
            method="update", resource_class=self.resource_class
        )
        Relationships = get_relationships_schema_for_resource_class(
            method="update", resource_class=self.resource_class
        )

        return JAUpdateRequest[Attributes, Relationships, Name]

    def get_create_model(self):
        Name = Literal[(self.resource_class.name,)]  # type: ignore

        Attributes = get_attributes_model_for_resource_class(
            method="create", resource_class=self.resource_class
        )
        Relationships = get_relationships_schema_for_resource_class(
            method="create", resource_class=self.resource_class
        )

        return JACreateRequest[Attributes, Relationships, Name]

    def get_resource(self, request: Request):
        inclusions: Inclusions = []
        include = request.query_params.get("include")

        if include:
            inclusions = [inclusion.split(".") for inclusion in include.split(",")]

        for relationship in self.resource_class.get_relationships().values():
            if relationship.direction != MANYTOONE:
                inclusions.append([relationship.field])

        return self.resource_class(
            inclusions=inclusions, **self.get_resource_kwargs(request=request)
        )

    def build_document_links(self, request: Request):
        path = request.url.path

        if query := request.url.query:
            path = f"{path}?{query}"

        return JALinks(self=path)

    def build_resource_object_links(
        self, id: str, resource: Union[Type[Resource], Resource]
    ):
        return JALinks(self=f"/{resource.plural_name}/{id}")

    def build_resource_identifier_object(
        self,
        related_obj: Optional[Object],
        resource: Union[Type[Resource], Resource],
        relationship_info: SQLModelRelationshipInfo,
    ) -> Optional[JAResourceIdentifierObject]:
        if not related_obj:
            return None

        return JAResourceIdentifierObject(
            type=resource.registry[
                relationship_info.schema_with_relationships.schema
            ].name,
            id=related_obj.id,
        )

    def build_resource_object_relationships(self, obj: Object, resource: Resource):
        relationships = {}

        for (
            relationship_name,
            relationship_info,
        ) in resource.get_relationships().items():
            links = JALinks(
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
            ]

            JARelationshipObject = (
                JARelationshipsObjectMany
                if relationship_info.many
                else JARelationshipsObjectSingle
            )

            if not relationship_info.many:
                data = data[0] if data else None

            relationships[relationship_name] = JARelationshipObject(
                links=links,
                data=data,
            )

        # If the relationship is to-one, then we can include `data`
        # But for to-many, we only include it if it's in inclusions.
        return relationships

    def build_resource_object(self, obj: Object, resource: Resource):
        valid_attributes = resource.get_attributes()

        # ID is a special case, so can ignored
        valid_attributes.remove("id")

        # Filter out relationships attributes
        attributes = {
            key: value
            for key, value in resource.Read.from_orm(obj).dict().items()
            if key in valid_attributes
        }

        resource_object = JAResourceObject(
            id=obj.id,
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
        rows: Union[Object, list[Object]],
        resource: Resource,
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
        data = data if many else data[0]

        # Get top-level resource links
        links = self.build_document_links(request=request)

        ResponseSchema = JAResponseList if many else JAResponseSingle

        return ResponseSchema(
            data=data, included=list(included_resources.values()), links=links
        )

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

    def parse_update(self, resource: Resource, update: dict):
        return super().parse_update(
            resource, self._parse_request_payload(payload=update)
        )

    def parse_create(self, resource: Resource, create: dict):
        return super().parse_update(
            resource, self._parse_request_payload(payload=create)
        )

    def _retrieve(
        self,
        *,
        id: Union[int, str],
        request: Request,
        include: Optional[str] = include_query,
    ):
        return super()._retrieve(id=id, request=request)

    def _list(self, *, request: Request, include: Optional[str] = include_query):
        return super()._list(request=request)

    def _create(
        self,
        *,
        create: base_router.TCreatePayload,
        request: Request,
        include: Optional[str] = include_query,
    ):
        return super()._create(create=create, request=request)

    def _update(
        self,
        *,
        id: Union[int, str],
        update: base_router.TUpdatePayload,
        request: Request,
        include: Optional[str] = include_query,
    ):
        return super()._update(id=id, update=update, request=request)

    def _delete(self, *, id: Union[int, str], request: Request):
        return super()._delete(id=id, request=request)

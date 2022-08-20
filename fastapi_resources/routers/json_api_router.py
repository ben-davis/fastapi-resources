from typing import Generic, List, Literal, Optional, Type, TypeVar, Union

from fastapi import Query, Request
from pydantic.generics import GenericModel
from pydantic.main import BaseModel

from fastapi_resources.resources.base_resource import Relationships, Resource
from fastapi_resources.resources.types import Inclusions
from fastapi_resources.routers import base_router

from .base_router import ResourceRouter

TRead = TypeVar("TRead", bound=BaseModel)
TName = TypeVar("TName", bound=str)
TIncluded = TypeVar("TIncluded")


class TIncludeParam(str):
    pass


class JALinks(BaseModel):
    """A links-object"""

    self: Optional[str]
    # Will be used when relationship endpoints are implemented
    related: Optional[str]


class JARelationshipsObject(BaseModel):
    links: list[JALinks]


class JAResourceObject(GenericModel, Generic[TRead, TName]):
    id: str
    type: TName
    attributes: TRead
    links: JALinks
    relationships: JARelationshipsObject


class JAResponseSingle(GenericModel, Generic[TRead, TName, TIncluded]):
    data: JAResourceObject[TRead, TName]
    included: TIncluded
    links: JALinks


class JAResponseList(GenericModel, Generic[TRead, TName, TIncluded]):
    data: List[JAResourceObject[TRead, TName]]
    included: TIncluded
    links: JALinks


include_query = Query(None, regex=r"^([\w\.]+)(,[\w\.]+)*$")


def get_schemas_from_relationships(
    relationships: Relationships, visited: set[type[BaseModel]] = None
):
    schemas = []
    visited = visited or set()
    for relationship_info in relationships.values():
        schema = relationship_info.schema_with_relationships.schema
        if schema in visited:
            continue

        visited.add(schema)
        schemas.append(schema)
        schemas += get_schemas_from_relationships(
            relationships=relationship_info.schema_with_relationships.relationships,
            visited=visited,
        )

    return schemas


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

    def get_included_schema(self) -> tuple[type[BaseModel], ...]:
        relationships = self.resource_class.get_relationships()
        schemas = get_schemas_from_relationships(relationships=relationships)

        return tuple(
            JAResourceObject[
                schema,
                Literal[(self.resource_class.registry[schema].name,)],
            ]
            for schema in schemas
        )

    def get_read_response_model(self):
        included_schemas = self.get_included_schema()
        Included = List[Union[included_schemas]] if included_schemas else list
        Read = self.resource_class.Read
        Name = Literal[(self.resource_class.name,)]

        return JAResponseSingle[Read, Name, Included]

    def get_list_response_model(self):
        included_schemas = self.get_included_schema()
        Included = List[Union[included_schemas]] if included_schemas else list
        Read = self.resource_class.Read
        Name = Literal[(self.resource_class.name,)]

        return JAResponseList[Read, Name, Included]

    def get_resource(self, request: Request):
        inclusions: Inclusions = []
        include = request.query_params.get("include")

        if include:
            inclusions = [inclusion.split(".") for inclusion in include.split(",")]

        return self.resource_class(inclusions=inclusions)

    def build_document_links(self, request: Request):
        path = request.url.path

        if query := request.url.query:
            path = f"{path}?{query}"

        return JALinks(self=path)

    def build_resource_object_links(
        self, id: str, resource: Union[Type[Resource], Resource]
    ):
        return JALinks(self=f"/{resource.plural_name}/{id}")

    def build_resource_object_relationships(
        self, id: str, resource: Union[Type[Resource], Resource]
    ):
        """
        links:
            self: a relationship link, e.g. /stars/123/relationships/planets
            related: /stars/123/planets
        data: [
            {
                type: planet
                id: 1
            },
            {
                type: planet
                id: 2
            },
        ]

        """
        links = []

        for relationship_name in resource.get_relationships():
            links.append(
                JALinks(
                    self=f"/{resource.plural_name}/{id}/relationships/{relationship_name}",
                    related=f"/{resource.plural_name}/{id}/{relationship_name}",
                )
            )

        # If the relationship is to-one, then we can include `data`
        # But for to-many, we only include it if it's in inclusions.
        return JARelationshipsObject(links=links)

    def build_response(
        self,
        rows: Union[BaseModel, list[BaseModel]],
        resource: Resource,
        request: Request,
    ):
        included_resources = {}

        many = isinstance(rows, list)
        rows = rows if isinstance(rows, list) else [rows]

        for row in rows:
            for inclusion in resource.inclusions:
                selected_objs = resource.get_related(obj=row, inclusion=inclusion)

                for selected_obj in selected_objs:
                    obj = selected_obj.obj
                    related_resource = selected_obj.resource

                    included_resources[
                        (related_resource.name, obj.id)
                    ] = JAResourceObject(
                        id=obj.id,
                        type=related_resource.name,
                        attributes=related_resource.Read.from_orm(obj),
                        links=self.build_resource_object_links(
                            id=obj.id, resource=related_resource
                        ),
                        relationships=self.build_resource_object_relationships(
                            id=obj.id, resource=related_resource
                        ),
                    )

        data = [
            JAResourceObject(
                id=row.id,
                attributes=row,
                type=resource.name,
                links=self.build_resource_object_links(id=row.id, resource=resource),
                relationships=self.build_resource_object_relationships(
                    id=row.id, resource=resource
                ),
            )
            for row in rows
        ]
        data = data if many else data[0]
        ResponseSchema = JAResponseList if many else JAResponseSingle

        # Get top-level resource links
        links = self.build_document_links(request=request)

        return ResponseSchema(
            data=data, included=list(included_resources.values()), links=links
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

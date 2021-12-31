from typing import Generic, List, Optional, TypeVar, Union

from fastapi import Query, Request, Response
from pydantic.generics import GenericModel
from pydantic.main import BaseModel

from fastapi_rest_framework.resources.base_resource import Relationships, Resource
from fastapi_rest_framework.resources.types import Inclusions
from fastapi_rest_framework.routers import base_router

from .base_router import ResourceRouter

TRead = TypeVar("TRead", bound=BaseModel)
TIncluded = TypeVar("TIncluded")


class TIncludeParam(str):
    pass


class JAResource(GenericModel, Generic[TRead]):
    id: str
    type: str
    attributes: TRead


class JAResponseSingle(GenericModel, Generic[TRead, TIncluded]):
    data: JAResource[TRead]
    included: List[TIncluded]


class JAResponseList(GenericModel, Generic[TRead, TIncluded]):
    data: List[JAResource[TRead]]
    included: List[TIncluded]


include_query = Query(None, regex=r"^([\w\.]+)(,[\w\.]+)*$")


def get_schemas_from_relationships(relationships: Relationships):
    schemas = []
    for relationship_info in relationships.values():
        schemas.append(relationship_info.schema_with_relationships.schema)
        schemas += get_schemas_from_relationships(
            relationships=relationship_info.schema_with_relationships.relationships,
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

        super().__init__(resource_class=resource_class, **kwargs)

    def get_included_schema(self) -> tuple[type[BaseModel], ...]:
        relationships = self.resource_class.get_relationships()
        schemas = get_schemas_from_relationships(relationships=relationships)

        return tuple(JAResource[schema] for schema in schemas)

    def get_read_response_model(self):
        included_schemas = self.get_included_schema()
        Included = Union[included_schemas]
        Read = self.resource_class.Read

        return JAResponseSingle[Read, Included]

    def get_list_response_model(self):
        included_schemas = self.get_included_schema()
        Included = Union[included_schemas]
        Read = self.resource_class.Read

        return JAResponseList[Read, Included]

    def get_resource(self, request: Request):
        inclusions: Inclusions = []
        include = request.query_params.get("include")

        if include:
            inclusions = [inclusion.split(".") for inclusion in include.split(",")]

        return self.resource_class(inclusions=inclusions)

    def build_response(
        self,
        rows: Union[BaseModel, list[BaseModel]],
        resource: Resource,
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

                    included_resources[obj.id] = JAResource(
                        id=selected_obj.obj.id,
                        type=related_resource.name,
                        attributes=resource.Read.from_orm(obj),
                    )

        data = [
            JAResource(id=row.id, attributes=row, type=resource.name) for row in rows
        ]
        data = data if many else data[0]
        ResponseSchema = JAResponseList if many else JAResponseSingle

        return ResponseSchema(
            data=data,
            included=list(included_resources.values()),
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
        super()._delete(id=id, request=request)

        return Response(status_code=204)

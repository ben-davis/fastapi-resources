from typing import Any, Generic, List, Literal, TypeVar, Union

from fastapi import Request
from pydantic.generics import GenericModel
from sqlmodel import SQLModel

from fastapi_rest_framework.resources.sqlmodel import SQLModelResource
from fastapi_rest_framework.resources.types import Inclusions
from fastapi_rest_framework.routers import base_router

from .base_router import ResourceRouter

TRead = TypeVar("TRead", bound=SQLModel)
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


class JSONAPIResourceRouter(ResourceRouter):
    def __init__(
        self,
        *,
        resource_class: type[SQLModelResource],
        **kwargs,
    ) -> None:
        self.resource_class = resource_class

        super().__init__(resource_class=resource_class, **kwargs)

    def get_included_schema(self):
        relationships = self.resource_class.get_relationships()
        return tuple(JAResource[r.schema] for r in relationships.values())

    def get_read_response_model(self):
        Included = self.get_included_schema()

        return JAResponseSingle[self.resource_class.Read, Union[Included]]

    def get_list_response_model(self):
        Included = self.get_included_schema()

        return JAResponseList[self.resource_class.Read, Union[Included]]

    def get_method_replacements(self):
        method_replacements = super().get_method_replacements()
        relationships = self.resource_class.get_relationships()

        include_param = {TIncludeParam: Literal[tuple(relationships.keys())]}

        return {
            "_create": {**method_replacements["_create"], **include_param},
            "_update": {**method_replacements["_update"], **include_param},
            "_retrieve": include_param,
            "_list": include_param,
        }

    def get_resource(self, request: Request):
        inclusions: Inclusions = []
        include = request.query_params.get("include")

        if include:
            inclusions = include.split(",")
            # inclusions = [inclusion.split(".") for inclusion in include.split(",")]

        return self.resource_class(request=request, inclusions=inclusions)

    # Feels like this is the actual thing that handles JSON-API.
    # Additionally, filters/sorting could be applied by override the `list` to provide extra
    # params.
    # But it would also requirea a different router to because the response models would be different
    # I suppose that could be something built by the resource
    def build_response(
        self,
        rows: Union[SQLModel, list[SQLModel]],
        resource: SQLModelResource,
    ):
        included_resources = {}

        many = isinstance(rows, list)
        rows = rows if isinstance(rows, list) else [rows]
        relationships = resource.get_relationships()

        for row in rows:
            for inclusion in resource.inclusions:
                included_objs = getattr(row, inclusion)
                if not included_objs:
                    continue

                included_objs = (
                    [included_objs]
                    if not isinstance(included_objs, list)
                    else included_objs
                )

                for included_obj in included_objs:
                    schema = relationships[inclusion].schema
                    included_resources[included_obj.id] = JAResource(
                        id=included_obj.id,
                        type=inclusion,
                        attributes=schema.from_orm(included_obj),
                    )

        data = [
            JAResource(id=row.id, attributes=row, type=resource.name) for row in rows
        ]
        data = data if many else data[0]
        ResponseSchema = JAResponseList if many else JAResponseSingle
        print(data)

        return ResponseSchema(
            data=data,
            included=list(included_resources.values()),
        )

    def _retrieve(
        self, *, id: Union[int, str], request: Request, include: TIncludeParam = None
    ):
        return super()._retrieve(id=id, request=request)

    def _list(self, *, request: Request, include: TIncludeParam = None):
        return super()._list(request=request)

    def _create(
        self,
        *,
        model: base_router.TCreate,
        request: Request,
        include: TIncludeParam = None,
    ):
        return super()._create(model=model, request=request)

    def _update(
        self,
        *,
        id: Union[int, str],
        model: base_router.TUpdate,
        request: Request,
        include: TIncludeParam = None,
    ):
        return super()._update(id=id, model=model, request=request)

    def _delete(
        self, *, id: Union[int, str], request: Request, include: TIncludeParam = None
    ):
        return super()._delete(id=id, request=request)

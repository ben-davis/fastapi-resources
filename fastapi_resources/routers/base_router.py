import inspect
from typing import (
    Any,
    Generic,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
    runtime_checkable,
)

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from fastapi_resources.resources.base_resource import Resource
from fastapi_resources.routers import decorators


class TCreatePayload(BaseModel):
    pass


class TUpdatePayload(BaseModel):
    pass


TResource = TypeVar("TResource", bound=Resource)


@runtime_checkable
class Action(Protocol):
    detail: bool
    methods: decorators.methods
    kwargs: dict[str, Any]

    def __call__(self):
        ...


class ResourceRouter(APIRouter, Generic[TResource]):
    resource_class: type[TResource]

    def __init__(
        self,
        *,
        resource_class: Optional[type[TResource]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        if resource_class:
            self.resource_class = resource_class

        self.method_replacements = self.get_method_replacements()
        self.ReadResponseModel = self.get_read_response_model()
        self.ListResponseModel = self.get_list_response_model()

        self._patch_route_types()
        self._link_routes()

    def get_read_response_model(self):
        return self.resource_class.Read

    def get_list_response_model(self):
        Read = self.resource_class.Read
        return List[Read]

    def get_method_replacements(self):
        return {
            "_create": {TCreatePayload: self.resource_class.Create},
            "_update": {TUpdatePayload: self.resource_class.Update},
        }

    def _patch_route_types(self):
        for method_name, replacements in self.method_replacements.items():
            method_instance = getattr(self, method_name, None)

            if not method_instance:
                continue

            original_signature = inspect.signature(method_instance)
            updated_params = [
                inspect.Parameter(
                    name=param.name,
                    kind=param.kind,
                    default=param.default,
                    annotation=replacements.get(param.annotation, param.annotation),
                )
                for param in original_signature.parameters.values()
            ]
            new_params = [
                inspect.Parameter(
                    name=key.replace("*", ""),
                    kind=inspect._ParameterKind.KEYWORD_ONLY,
                    default=None,
                    annotation=annotation,
                )
                for key, annotation in replacements.items()
                if isinstance(key, str) and key.startswith("*")
            ]
            updated_signature = inspect.Signature(updated_params + new_params)

            # Required to avoid closing over method_name
            def factory(_method_name):
                def wrapper(*args, **kwargs):
                    class_method = getattr(self.__class__, _method_name)
                    return class_method(self, *args, **kwargs)

                return wrapper

            setattr(self, method_name, factory(method_name))
            getattr(self, method_name).__signature__ = updated_signature

    def _link_routes(self):
        resource_class = self.resource_class

        self._link_actions()

        if resource_class.retrieve:
            self.get(
                f"/{{id}}",
                response_model=self.ReadResponseModel,
                response_model_exclude_unset=True,
                summary=f"Get {resource_class.name}",
            )(self._retrieve)

        if resource_class.list:
            self.get(
                f"",
                response_model=self.ListResponseModel,
                response_model_exclude_unset=True,
                summary=f"Get {resource_class.name} list",
            )(self._list)

        if resource_class.create:
            self.post(
                f"",
                response_model=self.ReadResponseModel,
                response_model_exclude_unset=True,
                summary=f"Create {resource_class.name}",
                status_code=201,
            )(self._create)

        if resource_class.update:
            self.patch(
                f"/{{id}}",
                response_model=self.ReadResponseModel,
                response_model_exclude_unset=True,
                summary=f"Update {resource_class.name}",
            )(self._update)

        if resource_class.delete:
            self.delete(f"/{{id}}", summary=f"Delete {resource_class.name}")(
                self._delete
            )

    def _link_actions(self):
        resource_class = self.resource_class

        for action in inspect.getmembers(object=self):
            name, func = action

            if not isinstance(func, Action):
                continue

            for method in func.methods:
                route_method = getattr(self, method)
                response_model = (
                    self.ReadResponseModel if func.detail else self.ListResponseModel
                )
                url = f"/{{id}}/{name}" if func.detail else f"/{name}"

                route_method(
                    url,
                    summary=f"{resource_class.name} {name}",
                    response_model=response_model,
                )(func)

    def get_resource(self, request: Request):
        return self.resource_class()

    def build_response(
        self,
        resource: Resource,
        rows: Union[BaseModel, List[BaseModel]],
        request: Request,
    ):
        return rows

    def perform_create(
        self, request: Request, resource: TResource, create: TCreatePayload
    ):
        if not resource.create:
            raise NotImplementedError("Resource.create not implemented")

        return resource.create(model=create)

    def perform_update(
        self,
        request: Request,
        resource: TResource,
        id: str | int,
        update: TUpdatePayload,
    ):
        if not resource.update:
            raise NotImplementedError("Resource.update not implemented")

        return resource.update(id=id, model=update)

    def perform_delete(self, request: Request, resource: TResource, id: str | int):
        if not resource.delete:
            raise NotImplementedError("Resource.delete not implemented")

        return resource.delete(id=id)

    def _retrieve(self, *, id: Union[int, str], request: Request):
        resource = self.get_resource(request=request)
        if not resource.retrieve:
            raise NotImplementedError("Resource.retrieve not implemented")

        row = resource.retrieve(id=id)
        return self.build_response(rows=row, resource=resource, request=request)

    def _list(self, *, request: Request):
        resource = self.get_resource(request=request)
        if not resource.list:
            raise NotImplementedError("Resource.list not implemented")

        rows = resource.list()
        return self.build_response(rows=rows, resource=resource, request=request)

    def _create(self, *, create: TCreatePayload, request: Request):
        resource = self.get_resource(request=request)

        row = self.perform_create(request=request, resource=resource, create=create)

        return self.build_response(rows=row, resource=resource, request=request)

    def _update(self, *, id: Union[int, str], update: TUpdatePayload, request: Request):
        resource = self.get_resource(request=request)

        row = self.perform_update(
            request=request, resource=resource, update=update, id=id
        )

        return self.build_response(rows=row, resource=resource, request=request)

    def _delete(self, *, id: Union[int, str], request: Request):
        resource = self.get_resource(request=request)

        self.perform_delete(request=request, resource=resource, id=id)

        return Response(status_code=204)

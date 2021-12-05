import inspect
from typing import List, Union

from fastapi import APIRouter, Request
from pydantic import BaseModel

from fastapi_rest_framework.resources.base_resource import Resource


class TCreate(BaseModel):
    pass


class TUpdate(BaseModel):
    pass


class ResourceRouter(APIRouter):
    def __init__(
        self,
        *,
        resource_class: type[Resource],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self.resource_class = resource_class

        self.method_replacements = self.get_method_replacements()
        self.ReadResponseModel = self.get_read_response_model()
        self.ListResponseModel = self.get_list_response_model()

        self._patch_route_types()
        self._link_routes(resource_class=resource_class)

    def get_read_response_model(self):
        return self.resource_class.Read

    def get_list_response_model(self):
        resource_class = self.resource_class
        return List[resource_class.Read]

    def get_method_replacements(self):
        return {
            "_create": {TCreate: self.resource_class.Create},
            "_update": {TUpdate: self.resource_class.Update},
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

    def _link_routes(self, resource_class: type[Resource]):
        if resource_class.retrieve:
            self.get(
                f"/{{id}}",
                response_model=self.ReadResponseModel,
                summary=f"Get {resource_class.name}",
            )(self._retrieve)

        if resource_class.list:
            self.get(
                f"/",
                response_model=self.ListResponseModel,
                summary=f"Get {resource_class.name} list",
            )(self._list)

        if resource_class.create:
            self.post(
                f"/",
                response_model=self.ReadResponseModel,
                summary=f"Create {resource_class.name}",
            )(self._create)

        if resource_class.update:
            self.patch(
                f"/{{id}}",
                response_model=self.ReadResponseModel,
                summary=f"Update {resource_class.name}",
            )(self._update)

        if resource_class.delete:
            self.delete(f"/{{id}}", summary=f"Delete {resource_class.name}")(
                self._delete
            )

    def get_resource(self, request: Request):
        return self.resource_class(request=request)

    def build_response(
        self, resource: Resource, rows: Union[BaseModel, List[BaseModel]]
    ):
        return rows

    def _retrieve(self, *, id: Union[int, str], request: Request):
        resource = self.get_resource(request=request)
        if not resource.retrieve:
            raise NotImplementedError("Resource.retrieve not implemented")

        row = resource.retrieve(id=id)
        return self.build_response(rows=row, resource=resource)

    def _list(self, *, request: Request):
        resource = self.get_resource(request=request)
        if not resource.list:
            raise NotImplementedError("Resource.list not implemented")

        rows = resource.list()
        return self.build_response(rows=rows, resource=resource)

    def _create(self, *, model: TCreate, request: Request):
        resource = self.get_resource(request=request)
        if not resource.create:
            raise NotImplementedError("Resource.create not implemented")

        row = resource.create(model=model)
        return self.build_response(rows=row, resource=resource)

    def _update(self, *, id: Union[int, str], model: TUpdate, request: Request):
        resource = self.get_resource(request=request)
        if not resource.update:
            raise NotImplementedError("Resource.update not implemented")

        row = resource.update(id=id, model=model)
        return self.build_response(rows=row, resource=resource)

    def _delete(self, *, id: Union[int, str], request: Request):
        resource = self.get_resource(request=request)
        if not resource.delete:
            raise NotImplementedError("Resource.delete not implemented")

        return resource.delete(id=id)


"""
    Question: how to allow the resource to receive pre-parsed inclusions as that
    should be specific to the router.

    Can it be added to ther request?

    But then it won't be available to FastAPI for docs/processing by pydantic.

    I think it would have to be added via functool.wraps

    That's what I was thinking the resource should be non-route specific and instead the
    routes are built once the resource is available.

    I think it could be constructed via a middleware and then added to the request.

    It does make more sense for the router to create the routes as then the jsonapi specific router
    would easily be able to add sorting/filtering etc.
"""

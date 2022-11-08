import inspect
from typing import (
    Any,
    Callable,
    Generic,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
    runtime_checkable,
)

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel

from fastapi_resources.resources.sqlmodel.exceptions import NotFound
from fastapi_resources.resources.types import ResourceProtocol
from fastapi_resources.routers import decorators


class TCreatePayload(BaseModel):
    pass


class TUpdatePayload(BaseModel):
    pass


TResource = TypeVar("TResource", bound=ResourceProtocol)


@runtime_checkable
class Action(Protocol):
    detail: bool
    methods: decorators.methods
    kwargs: dict[str, Any]

    def __call__(self):
        ...


class ResourceRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                response: Response = await original_route_handler(request)
            except NotFound as exc:
                raise HTTPException(status_code=404, detail=str(exc))

            if resource := getattr(request, "resource", None):
                resource.close()

            return response

        return custom_route_handler


class ResourceRouter(APIRouter, Generic[TResource]):
    resource_class: type[TResource]
    route_class: type[ResourceRoute] = ResourceRoute

    def __init__(
        self,
        *,
        resource_class: Optional[type[TResource]] = None,
        **kwargs,
    ) -> None:
        super().__init__(route_class=self.route_class, **kwargs)

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

    def get_update_model(self):
        return self.resource_class.Update

    def get_create_model(self):
        return self.resource_class.Create

    def get_method_replacements(self):
        return {
            "_create": {TCreatePayload: self.get_create_model()},
            "_update": {TUpdatePayload: self.get_update_model()},
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
                async def wrapper(*args, **kwargs):
                    class_method = getattr(self.__class__, _method_name)
                    return await class_method(self, *args, **kwargs)

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
        kwargs = self.get_resource_kwargs(request=request)
        resource = self.resource_class(**kwargs)

        setattr(request, "resource", resource)

        return resource

    def get_resource_context(self, request: Request):
        return {"request": request}

    def get_resource_kwargs(self, request: Request):
        return {"context": self.get_resource_context(request=request)}

    def build_response(
        self,
        resource: TResource,
        rows: Union[BaseModel, List[BaseModel]],
        request: Request,
    ):
        return rows

    def parse_update(
        self,
        resource: TResource,
        update: dict,
    ):
        resource_relationships = resource.get_relationships()

        relationships = {}

        for field in list(update.keys()):
            value = update[field]
            if field in resource_relationships:
                relationships[field] = value
                del update[field]

        return update, relationships

    def perform_create(
        self,
        request: Request,
        resource: TResource,
        attributes: dict,
        relationships: dict,
    ):
        if not resource.create:
            raise NotImplementedError("Resource.create not implemented")

        return resource.create(attributes=attributes, relationships=relationships)

    def perform_update(
        self,
        request: Request,
        resource: TResource,
        id: str | int,
        attributes: dict,
        relationships: dict,
    ):
        if not resource.update:
            raise NotImplementedError("Resource.update not implemented")

        return resource.update(
            id=id, attributes=attributes, relationships=relationships
        )

    def perform_delete(self, request: Request, resource: TResource, id: str | int):
        if not resource.delete:
            raise NotImplementedError("Resource.delete not implemented")

        return resource.delete(id=id)

    async def _retrieve(self, *, id: Union[int, str], request: Request):
        resource = self.get_resource(request=request)
        if not resource.retrieve:
            raise NotImplementedError("Resource.retrieve not implemented")

        row = resource.retrieve(id=id)
        return self.build_response(rows=row, resource=resource, request=request)

    async def _list(self, *, request: Request):
        resource = self.get_resource(request=request)
        if not resource.list:
            raise NotImplementedError("Resource.list not implemented")

        rows = resource.list()
        return self.build_response(rows=rows, resource=resource, request=request)

    async def _create(self, *, create: TCreatePayload, request: Request):
        resource = self.get_resource(request=request)

        attributes, relationships = self.parse_update(
            resource=resource, update=create.dict(exclude_unset=True)
        )

        row = self.perform_create(
            request=request,
            resource=resource,
            attributes=attributes,
            relationships=relationships,
        )

        return self.build_response(rows=row, resource=resource, request=request)

    async def _update(
        self, *, id: Union[int, str], update: TUpdatePayload, request: Request
    ):
        resource = self.get_resource(request=request)

        attributes, relationships = self.parse_update(
            resource=resource, update=update.dict(exclude_unset=True)
        )
        row = self.perform_update(
            request=request,
            resource=resource,
            attributes=attributes,
            relationships=relationships,
            id=id,
        )

        return self.build_response(rows=row, resource=resource, request=request)

    async def _delete(self, *, id: Union[int, str], request: Request):
        resource = self.get_resource(request=request)

        self.perform_delete(request=request, resource=resource, id=id)

        return Response(status_code=204)

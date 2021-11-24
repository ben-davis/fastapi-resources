import dataclasses
import inspect
import typing
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
)

from fastapi import APIRouter, HTTPException, Request
from pydantic.generics import GenericModel
from sqlalchemy.future.engine import Engine
from sqlalchemy.orm import joinedload
from sqlmodel import Session, SQLModel, select
from sqlmodel.sql.expression import SelectOfScalar

TCreate = TypeVar("TCreate", bound=SQLModel)
TUpdate = TypeVar("TUpdate", bound=SQLModel)
TRead = TypeVar("TRead", bound=SQLModel)
TDb = TypeVar("TDb", bound=SQLModel)
TIncludeParam = TypeVar("TIncludeParam", bound=str, contravariant=True)
TypeVarType = Any


@dataclasses.dataclass
class Relationship:
    schema: SQLModel
    many: bool


class JAResource(GenericModel, Generic[TRead]):
    id: str
    type: str
    attributes: TRead


TJAResource = TypeVar("TJAResource")


class JAResponseSingle(GenericModel, Generic[TJAResource]):
    data: TJAResource
    # Todo
    included: List[dict]


class JAResponseList(GenericModel, Generic[TJAResource]):
    data: List[TJAResource]
    # Todo
    included: List[dict]


class DBSQLModel(Protocol):
    id: Union[str, int]


class GetInclusions(Protocol, Generic[TIncludeParam]):
    def __call__(self, request: Request, include: TIncludeParam = None) -> list[str]:
        ...


class GetSelect(Protocol):
    def __call__(
        self, request: Request, inclusions: Optional[list[str]] = None
    ) -> SelectOfScalar:
        ...


class BuildResponse(Protocol, Generic[TDb]):
    def __call__(
        self, rows: list[TDb], request: Request, inclusions: list[str]
    ) -> Union[JAResponseSingle, JAResponseList]:
        ...


class SQLResource(Protocol, Generic[TDb, TIncludeParam]):
    name: str
    engine: Engine

    relationships: dict[str, Relationship] = {}

    Db: Type[SQLModel]
    Read: Type[SQLModel]

    Create: Optional[Type[SQLModel]]
    Update: Optional[Type[SQLModel]]

    create: Optional[Callable]
    list: Optional[Callable]
    update: Optional[Callable]
    delete: Optional[Callable]
    retrieve: Optional[Callable]

    get_select: GetSelect
    get_inclusions: GetInclusions[TIncludeParam]
    build_response: BuildResponse[TDb]


class BaseSQLResource(SQLResource, Generic[TDb]):
    def __init__(self, *args, **kwargs):
        # # Build the relationships for the Db model
        annotations = typing.get_type_hints(self.Db)
        relationship_fields = self.Db.__sqlmodel_relationships__.keys()
        self.relationships = {
            field: typing.get_args(annotations[field])[0]
            for field in relationship_fields
        }

        for field in relationship_fields:
            annotated_type = annotations[field]
            many = typing.get_origin(annotated_type) == list

            self.relationships[field] = Relationship(
                schema=typing.get_args(annotated_type)[0],
                many=many,
            )

        # Params to replace
        methods = {
            "create": {TCreate: self.Create},
            "update": {TUpdate: self.Update},
            "retrieve": {TIncludeParam: Literal[tuple(relationship_fields)]},
            "list": {TIncludeParam: Literal[tuple(relationship_fields)]},
        }

        for method_name, replacements in methods.items():
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
            updated_signature = inspect.Signature(updated_params)

            # Required to avoid closing over method_name
            def factory(_method_name):
                def wrapper(*args, **kwargs):
                    class_method = getattr(self.__class__, _method_name)
                    return class_method(self, *args, **kwargs)

                return wrapper

            setattr(self, method_name, factory(method_name))
            getattr(self, method_name).__signature__ = updated_signature

        return super().__init__(*args, **kwargs)

    def get_inclusions(self, request: Request, include: str = None):
        # TODO: Support nested
        return include.split(",") if include else []

    def get_select(self, request: Request, inclusions: Optional[list[str]] = None):
        options = []
        inclusions = inclusions or []

        # Build the query options based on the include
        for inclusion in inclusions:
            options.append(joinedload(getattr(self.Db, inclusion)))

        return select(self.Db).options(*options)

    def build_response(self, rows: list[TDb], request: Request, inclusions: list[str]):
        included_resources = {}
        rows = rows if isinstance(rows, list) else [rows]

        for row in rows:
            for inclusion in inclusions:
                included_objs = getattr(row, inclusion)
                if not included_objs:
                    continue

                included_objs = (
                    [included_objs]
                    if not isinstance(included_objs, list)
                    else included_objs
                )

                for included_obj in included_objs:
                    schema = self.relationships[inclusion].schema
                    included_resources[included_obj.id] = JAResource(
                        id=included_obj.id,
                        type=inclusion,
                        attributes=schema.from_orm(included_obj),
                    )

        data = [JAResource(id=row.id, attributes=row, type=self.name) for row in rows]

        return JAResponseSingle(
            data=data if len(data) > 1 else data[0],
            included=list(included_resources.values()),
        )


class CreateResourceMixin(Generic[TCreate]):
    def create(self: SQLResource, model: TCreate):
        with Session(self.engine) as session:
            row = self.Db.from_orm(model)
            session.add(row)
            session.commit()
            session.refresh(row)

            return JAResponseSingle(
                data=JAResource(id=row.id, attributes=row, type=self.name), included=[]
            )


class UpdateResourceMixin(Generic[TUpdate, TIncludeParam]):
    def update(
        self: SQLResource,
        *,
        id: int,
        model: TUpdate,
        request: Request,
        include: TIncludeParam = None,
    ):
        with Session(self.engine) as session:
            inclusions = self.get_inclusions(request=request, include=include)
            select = self.get_select(request=request, inclusions=inclusions)

            row = session.exec(select.where(self.Db.id == id)).unique().one()

            if not row:
                raise HTTPException(status_code=404, detail=f"{self.name} not found")

            data = model.dict(exclude_unset=True)
            for key, value in data.items():
                setattr(row, key, value)

            session.add(row)
            session.commit()
            session.refresh(row)

            return self.build_response(
                rows=[row],
                request=request,
                inclusions=inclusions,
            )


class ListResourceMixin(Generic[TIncludeParam]):
    def list(self: SQLResource, request: Request, include: TIncludeParam = None):
        with Session(self.engine) as session:
            inclusions = self.get_inclusions(request=request, include=include)
            select = self.get_select(request=request, inclusions=inclusions)

            rows = session.exec(select).all()

            return self.build_response(
                rows=rows,
                request=request,
                inclusions=inclusions,
            )


class RetrieveResourceMixin(Generic[TIncludeParam]):
    def retrieve(
        self: SQLResource, *, id: int, include: TIncludeParam = None, request: Request
    ):
        with Session(self.engine) as session:
            inclusions = self.get_inclusions(request=request, include=include)
            select = self.get_select(request=request, inclusions=inclusions)

            row = session.exec(select.where(self.Db.id == id)).unique().one()

            if not row:
                raise HTTPException(
                    status_code=404, detail=f"{self.name.title()} not found"
                )

            return self.build_response(
                rows=[row],
                request=request,
                inclusions=inclusions,
            )


class DeleteResourceMixin:
    def delete(self: SQLResource, *, id: int, request: Request):
        with Session(self.engine) as session:
            select = self.get_select(request=request)
            row = session.exec(select.where(self.Db.id == id)).unique().one()

            if not row:
                raise HTTPException(status_code=404, detail=f"{self.name} not found")

            session.delete(row)
            session.commit()

            return {"ok": True}


class ListCreateResource(CreateResourceMixin, ListResourceMixin, BaseSQLResource):
    pass


class ListCreateUpdateResource(
    ListResourceMixin,
    CreateResourceMixin,
    UpdateResourceMixin,
    BaseSQLResource,
    Generic[TCreate, TUpdate],
):
    pass


class FullResource(
    RetrieveResourceMixin,
    ListResourceMixin,
    CreateResourceMixin,
    UpdateResourceMixin,
    DeleteResourceMixin,
    BaseSQLResource,
    Generic[TCreate, TUpdate],
):
    pass


class ResourceRouter(APIRouter):
    def __init__(
        self,
        *,
        resource: SQLResource,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        Read = resource.Read

        if resource.retrieve:
            self.get(
                f"/{{id}}",
                response_model=JAResponseSingle[JAResource[Read]],
                summary=f"Get {resource.name}",
            )(resource.retrieve)

        if resource.list:

            self.get(
                f"/",
                response_model=JAResponseList[JAResource[Read]],
                summary=f"Get {resource.name} list",
            )(resource.list)

        if resource.create:
            self.post(
                f"/",
                response_model=JAResponseSingle[JAResource[Read]],
                summary=f"Create {resource.name}",
            )(resource.create)

        if resource.update:
            self.patch(
                f"/{{id}}",
                response_model=JAResponseSingle[JAResource[Read]],
                summary=f"Update {resource.name}",
            )(resource.update)

        if resource.delete:
            self.delete(f"/{{id}}", summary=f"Delete {resource.name}")(resource.delete)

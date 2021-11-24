import dataclasses
import inspect
import typing
from typing import (
    Any,
    Callable,
    Generic,
    List,
    Literal,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
)

from fastapi import APIRouter, HTTPException
from pydantic.generics import GenericModel
from sqlalchemy.future.engine import Engine
from sqlalchemy.orm import joinedload
from sqlmodel import Session, SQLModel, select

TCreate = TypeVar("TCreate", bound=SQLModel)
TUpdate = TypeVar("TUpdate", bound=SQLModel)
TRead = TypeVar("TRead", bound=SQLModel)
TIncludeParam = TypeVar("TIncludeParam", bound=str)
TypeVarType = Any


@dataclasses.dataclass
class Relationship:
    schema: SQLModel
    many: bool


class JAResource(GenericModel, Generic[TRead]):
    id: Union[str, int]
    type: str
    attributes: TRead


TJAResource = TypeVar("TJAResource")


class JAResponse(GenericModel, Generic[TJAResource]):
    data: TJAResource
    # Todo
    included: List[dict]


class DBSQLModel(SQLModel):
    id: str | int


class SQLResource(Protocol):
    name: str
    engine: Engine

    relationships: dict[str, Relationship] = {}

    Db: Type[DBSQLModel]
    Read: Type[SQLModel]

    Create: Optional[Type[SQLModel]]
    Update: Optional[Type[SQLModel]]

    create: Optional[Callable]
    list: Optional[Callable]
    update: Optional[Callable]
    delete: Optional[Callable]
    retrieve: Optional[Callable]


class BaseSQLResource:
    def __init__(self: SQLResource, *args, **kwargs):
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


class CreateResourceMixin(Generic[TCreate]):
    def create(self: SQLResource, model: TCreate):
        with Session(self.engine) as session:
            row = self.Db.from_orm(model)
            session.add(row)
            session.commit()
            session.refresh(row)

            return JAResponse(data=JAResource(id=row.id, attributes=row, type=self.name), included=[])


class UpdateResourceMixin(Generic[TUpdate]):
    def update(
        self: SQLResource,
        *,
        id: int,
        model: TUpdate,
    ):
        with Session(self.engine) as session:
            row = session.get(self.Db, id)

            if not row:
                raise HTTPException(status_code=404, detail=f"{self.name} not found")

            data = model.dict(exclude_unset=True)
            for key, value in data.items():
                setattr(row, key, value)

            session.add(row)
            session.commit()
            session.refresh(row)

            row = session.exec(select(self.Db).where(self.Db.id == id)).one()

            return row


class ListResourceMixin(Generic[TIncludeParam]):
    def list(self: SQLResource, include: TIncludeParam = None):
        with Session(self.engine) as session:
            rows = session.exec(select(self.Db)).all()
            return rows


class RetrieveResourceMixin(Generic[TIncludeParam]):
    def retrieve(self: SQLResource, *, id: int, include: TIncludeParam = None):
        with Session(self.engine) as session:
            inclusions = include.split(',') if include else []
            options = []

            # Build the query options based on the include
            for inclusion in inclusions:
                options.append(joinedload(
                    getattr(self.Db, inclusion)
                ))

            row = session.exec(select(self.Db).where(self.Db.id == id).options(*options)).unique().one()
            if not row:
                raise HTTPException(
                    status_code=404, detail=f"{self.name.title()} not found"
                )

            included = []
            for inclusion in inclusions:
                included_objs = getattr(row, inclusion)
                included_objs = [included_objs] if not isinstance(included_objs, list) else included_objs

                for included_obj in included_objs:
                    schema = self.relationships[inclusion].schema
                    included.append(
                        JAResource(
                            id=included_obj.id,
                            type=inclusion,
                            attributes=schema.from_orm(included_obj)
                        )
                    )

            return JAResponse(data=JAResource(id=id, attributes=row, type=self.name), included=included)


class DeleteResourceMixin:
    def delete(self: SQLResource, *, id: int):
        with Session(self.engine) as session:
            row = session.get(self.Db, id)
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
                response_model=JAResponse[JAResource[Read]],
                summary=f"Get {resource.name}",
            )(resource.retrieve)

        if resource.list:
            Read = resource.Read
            self.get(
                f"/", response_model=List[Read], summary=f"Get {resource.name} list"
            )(resource.list)

        if resource.create:
            self.post(
                f"/", response_model=JAResponse[JAResource[Read]], summary=f"Create {resource.name}"
            )(resource.create)

        if resource.update:
            self.patch(
                f"/{{id}}",
                response_model=resource.Read,
                summary=f"Update {resource.name}",
            )(resource.update)

        if resource.delete:
            self.delete(f"/{{id}}", summary=f"Delete {resource.name}")(resource.delete)

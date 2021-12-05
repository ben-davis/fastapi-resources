import operator
import typing
from dataclasses import dataclass
from typing import Any, ClassVar, Optional, Protocol, Type

from fastapi import HTTPException
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import exc as sa_exceptions
from sqlalchemy.orm import joinedload
from sqlmodel import Session, SQLModel, select
from sqlmodel.sql.expression import SelectOfScalar

from fastapi_rest_framework.resources import base_resource, types


class GetSelect(Protocol):
    def __call__(self) -> SelectOfScalar:
        ...


class GetObject(Protocol):
    def __call__(
        self,
        id: int | str,
        session: Session,
    ) -> SQLModel:
        ...


@dataclass
class SQLModelRelationship:
    schema: Type[SQLModel]
    many: bool


class SQLResourceProtocol(types.ResourceProtocol, Protocol):
    engine: ClassVar[Engine]

    Db: ClassVar[Type[SQLModel]]
    Read: ClassVar[Type[SQLModel]]
    relationships: ClassVar[dict[str, SQLModelRelationship]]

    Create: ClassVar[Optional[Type[SQLModel]]]
    Update: ClassVar[Optional[Type[SQLModel]]]

    get_select: GetSelect
    get_object: GetObject


def get_related_schema(annotation: Any):
    args = typing.get_args(annotation)
    if args:
        generic_arg = args[0]
        if issubclass(generic_arg, SQLModel):
            # Generic assumes first arg is the model
            return generic_arg

        raise ValueError("Unsupported generic relationship type. Must be a single arg.")

    if issubclass(annotation, SQLModel):
        return annotation

    raise ValueError(f"Unsupported relationship type {annotation}")


class BaseSQLResource(base_resource.Resource):
    engine: ClassVar[Engine]

    Db: ClassVar[Type[SQLModel]]
    Read: ClassVar[Type[SQLModel]]

    Create: ClassVar[Optional[Type[SQLModel]]]
    Update: ClassVar[Optional[Type[SQLModel]]]

    @classmethod
    def get_relationships(cls) -> dict[str, SQLModelRelationship]:
        # # Build the relationships for the Db model
        annotations = typing.get_type_hints(cls.Db)
        relationship_fields = cls.Db.__sqlmodel_relationships__.keys()

        relationships = {}

        # TODO: Support nested
        for field in relationship_fields:
            annotated_type = annotations[field]
            related_schema = get_related_schema(annotated_type)

            # TODO: Use related_schema to build nested, stopping if its circular
            many = typing.get_origin(annotated_type) == list

            relationships[field] = SQLModelRelationship(
                schema=related_schema,
                many=many,
            )

        return relationships

    def get_select(self):
        options = []
        inclusions = self.inclusions or []

        # Build the query options based on the include
        for inclusion in inclusions:
            attr = operator.attrgetter(".".join([inclusion]))(self.Db)
            options.append(joinedload(attr))

        return select(self.Db).options(*options)

    def get_object(
        self,
        session: Session,
        id: int | str,
    ):
        select = self.get_select()

        try:
            return session.exec(select.where(self.Db.id == id)).unique().one()
        except sa_exceptions.NoResultFound:
            raise HTTPException(status_code=404, detail=f"{self.name} not found")


class CreateResourceMixin:
    def create(
        self: SQLResourceProtocol,
        model: SQLModel,
    ):
        with Session(self.engine) as session:
            row = self.Db.from_orm(model)
            session.add(row)
            session.commit()

            row = self.get_object(id=row.id, session=session)

            return row


class UpdateResourceMixin:
    def update(
        self: SQLResourceProtocol,
        *,
        id: int | str,
        model: SQLModel,
    ):
        with Session(self.engine) as session:
            row = self.get_object(id=id, session=session)

            data = model.dict(exclude_unset=True)
            for key, value in data.items():
                setattr(row, key, value)

            session.add(row)
            session.commit()
            session.refresh(row)

            return row


class ListResourceMixin:
    def list(self: SQLResourceProtocol):
        with Session(self.engine) as session:
            select = self.get_select()

            rows = session.exec(select).unique().all()

            return rows


class RetrieveResourceMixin:
    def retrieve(self: SQLResourceProtocol, *, id: int | str):
        with Session(self.engine) as session:
            row = self.get_object(id=id, session=session)

            return row


class DeleteResourceMixin:
    def delete(self: SQLResourceProtocol, *, id: int | str):
        with Session(self.engine) as session:
            row = self.get_object(id=id, session=session)

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
):
    pass


class SQLModelResource(
    RetrieveResourceMixin,
    ListResourceMixin,
    CreateResourceMixin,
    UpdateResourceMixin,
    DeleteResourceMixin,
    BaseSQLResource,
):
    pass

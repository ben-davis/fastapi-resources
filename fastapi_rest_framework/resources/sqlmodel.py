import copy
import operator
import typing
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, Optional, Protocol, Type, TypeVar

from fastapi import HTTPException
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import exc as sa_exceptions
from sqlalchemy.orm import joinedload
from sqlmodel import Session, SQLModel, select
from sqlmodel.sql.expression import SelectOfScalar

from fastapi_rest_framework.resources import base_resource, types


@dataclass
class SchemaWithRelationships:
    schema: Type[SQLModel]
    relationships: "Relationships"


@dataclass
class SQLModelRelationshipInfo:
    schema_with_relationships: SchemaWithRelationships
    many: bool
    field: str


Relationships = dict[str, SQLModelRelationshipInfo]


TDb = TypeVar("TDb", bound=SQLModel)


class SQLResourceProtocol(types.ResourceProtocol, Protocol, Generic[TDb]):
    Db: ClassVar[Type[TDb]]
    Read: ClassVar[Type[SQLModel]]

    Create: ClassVar[Optional[Type[SQLModel]]]
    Update: ClassVar[Optional[Type[SQLModel]]]

    session: Session

    @classmethod
    def get_relationships(
        cls,
    ) -> dict[str, SQLModelRelationshipInfo]:
        ...

    def get_related(self, obj: SQLModel, field: str) -> SQLModel | list[SQLModel]:
        ...

    def get_object(self, id: int | str) -> SQLModel:
        ...

    def get_select(self) -> SelectOfScalar[SQLModel]:
        ...


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


def get_relationships_from_schema(
    schema: Type[SQLModel],
    schema_cache: Optional[
        dict[
            tuple[Optional[str], Type[SQLModel]],
            SchemaWithRelationships,
        ]
    ] = None,
    immediate_parent_backpopulated_field: Optional[str] = None,
    parent_key: Optional[str] = None,
):
    schema_cache = schema_cache or {}

    annotations = typing.get_type_hints(schema)
    relationship_fields = schema.__sqlmodel_relationships__.keys()
    relationships = {}

    parent_schema_with_relationships = SchemaWithRelationships(
        schema=schema,
        relationships=relationships,
    )

    # Just a sanity check. This function should never be called for a relationship
    # that already exists.
    assert (parent_key, schema) not in schema_cache

    schema_cache[(parent_key, schema)] = parent_schema_with_relationships

    for field in relationship_fields:
        annotated_type = annotations[field]
        related_schema = get_related_schema(annotated_type)

        new_parent_key = f"{schema}.{field}"

        many = typing.get_origin(annotated_type) == list

        # If this branch already contains the schema with the same parent,
        # we can reuse the relationship to avoid a cycle.
        if relationship_info := schema_cache.get((new_parent_key, related_schema)):
            relationships[field] = SQLModelRelationshipInfo(
                schema_with_relationships=relationship_info,
                many=many,
                field=field,
            )
            continue

        # For any relationship, the child will have a backpopulated reference
        # to the parent; we want to exclude that from available relationships
        if field == immediate_parent_backpopulated_field:
            continue

        backpopulated_field = schema.__sqlmodel_relationships__[field].back_populates

        get_relationships_from_schema(
            schema=related_schema,
            schema_cache=schema_cache,
            immediate_parent_backpopulated_field=backpopulated_field,
            parent_key=new_parent_key,
        )

        # After the above function has been called, the relationship
        # will have been created. But we want to use it without having
        # to return the object, so we just grab it from cache. A cleaner
        # solution is to overload the signature based on whether
        # `parent_field` is passed in,
        schema_with_relationship = schema_cache.get((new_parent_key, related_schema))
        assert schema_with_relationship

        relationships[field] = SQLModelRelationshipInfo(
            schema_with_relationships=schema_with_relationship,
            many=many,
            field=field,
        )

    return relationships


# Galaxy - > stars -> planets -> star -> LOOP


class BaseSQLResource(base_resource.Resource, SQLResourceProtocol[TDb], Generic[TDb]):
    def __init__(
        self,
        session: Session,
        inclusions: Optional[types.Inclusions] = None,
        *args,
        **kwargs,
    ):
        self.session = session

        super().__init__(inclusions=inclusions)

    @classmethod
    def get_relationships(cls) -> dict[str, SQLModelRelationshipInfo]:
        """
        Okay so:
        - we want to return a list of all valid relationships, regardles
        of depth.
        - It needs to terminate before any cycles
        - each step of the relationship needs to have an associated schema
        - It should be done via a metaclass so it's done during class creation
        """
        return get_relationships_from_schema(schema=cls.Db)

    def get_select(self):
        options = []
        inclusions = self.inclusions or []

        # Build the query options based on the include
        for inclusion in inclusions:
            attr = operator.attrgetter(".".join(inclusion))(self.Db)
            options.append(joinedload(attr))

        return select(self.Db).options(*options)

    def get_object(
        self,
        id: int | str,
    ) -> SQLModel:
        select = self.get_select()

        try:
            return self.session.exec(select.where(self.Db.id == id)).unique().one()
        except sa_exceptions.NoResultFound:
            raise HTTPException(status_code=404, detail=f"{self.name} not found")

    def get_related(
        self,
        obj: SQLModel,
        field: str,
    ):
        return getattr(obj, field)


class CreateResourceMixin:
    def create(
        self: SQLResourceProtocol,
        model: SQLModel,
    ):
        row = self.Db.from_orm(model)
        self.session.add(row)
        self.session.commit()

        row = self.get_object(id=row.id)

        return row


class UpdateResourceMixin:
    def update(
        self: SQLResourceProtocol,
        *,
        id: int | str,
        model: SQLModel,
    ):
        row = self.get_object(id=id)

        data = model.dict(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)

        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        return row


class ListResourceMixin:
    def list(self: SQLResourceProtocol):
        select = self.get_select()

        rows = self.session.exec(select).unique().all()

        return rows


class RetrieveResourceMixin:
    def retrieve(self: SQLResourceProtocol, *, id: int | str):
        row = self.get_object(id=id)

        return row


class DeleteResourceMixin:
    def delete(self: SQLResourceProtocol, *, id: int | str):
        row = self.get_object(id=id)

        self.session.delete(row)
        self.session.commit()

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
    BaseSQLResource[TDb],
    Generic[TDb],
):
    pass

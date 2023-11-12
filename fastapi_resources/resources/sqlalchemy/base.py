import copy
from typing import Any, ClassVar, Generic, Optional, Type

from sqlalchemy import exc as sa_exceptions
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import MANYTOONE, DeclarativeBase, Session, joinedload

from fastapi_resources.resources import base_resource
from fastapi_resources.resources.sqlalchemy.exceptions import NotFound

from . import types


def get_relationships_from_schema(
    schema: Type[DeclarativeBase],
    schema_cache: Optional[
        dict[
            tuple[Optional[str], Type[DeclarativeBase]],
            types.SchemaWithRelationships,
        ]
    ] = None,
    immediate_parent_backpopulated_field: Optional[str] = None,
    parent_key: Optional[str] = None,
):
    schema_cache = schema_cache or {}

    relationships = {}

    parent_schema_with_relationships = types.SchemaWithRelationships(
        schema=schema,
        relationships=relationships,
    )

    # Just a sanity check. This function should never be called for a relationship
    # that already exists.
    assert (parent_key, schema) not in schema_cache

    schema_cache[(parent_key, schema)] = parent_schema_with_relationships

    for field, sqlalchemy_relationship in inspect(schema).relationships.items():
        related_schema = sqlalchemy_relationship.mapper.class_
        many = sqlalchemy_relationship.uselist

        # Used to uniquely identify the related schema relative to a parent
        new_parent_key = f"{schema}.{field}"

        # TODO: Handle MANYTOMANY
        direction = sqlalchemy_relationship.direction
        update_field = list(
            sqlalchemy_relationship.local_columns
            if direction == MANYTOONE
            else sqlalchemy_relationship.remote_side
        )[0].name

        # If this branch already contains the schema with the same parent,
        # we can reuse the relationship to avoid a cycle.
        if relationship_info := schema_cache.get((new_parent_key, related_schema)):
            relationships[field] = types.SQLAlchemyRelationshipInfo(
                schema_with_relationships=relationship_info,
                many=many,
                field=field,
                direction=direction,
                update_field=update_field,
            )
            continue

        # For any relationship, the child will have a backpopulated reference
        # to the parent; we want to exclude that from available relationships
        if field == immediate_parent_backpopulated_field:
            continue

        # TODO: Can we cache the relationships when added to the registry?
        backpopulated_field = inspect(schema).relationships[field].back_populates

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

        relationships[field] = types.SQLAlchemyRelationshipInfo(
            schema_with_relationships=schema_with_relationship,
            many=many,
            field=field,
            direction=direction,
            update_field=update_field,
        )

    return relationships


class BaseSQLAlchemyResource(
    base_resource.Resource[types.TDb],
    types.SQLAlchemyResourceProtocol[types.TDb],
    Generic[types.TDb],
):
    registry: dict[Type[DeclarativeBase], type["BaseSQLAlchemyResource"]] = {}

    Paginator: ClassVar[Optional[Type[types.PaginatorProtocol]]]
    paginator: Optional[types.PaginatorProtocol]

    id_field: Optional[str] = None

    def __init_subclass__(cls) -> None:
        if Db := getattr(cls, "Db", None):
            BaseSQLAlchemyResource.registry[Db] = cls

        return super().__init_subclass__()

    def __init__(
        self,
        session: Session = None,
        inclusions: Optional[types.Inclusions] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        *args,
        **kwargs,
    ):
        if session:
            self.session = session
        else:
            assert self.engine, "A session or an engine must be given."
            self.session = Session(self.engine)

        # TODO: Save the relationships on the instance at instantiation for caching

        if Paginator := getattr(self, "Paginator", None):
            self.paginator = Paginator(cursor=cursor, limit=limit)

        super().__init__(inclusions=inclusions, *args, **kwargs)

    def close(self):
        self.session.close()

    @classmethod
    def get_relationships(cls) -> types.Relationships:
        """Builds the relationship graph for the current resource.

        TODO: Have the relationship point to the resource, rather than the schema. Use
            the registry to lookup the related resource.

        Used to:
          - Validate a given inclusion resolves to a relationship (done in the base class)
          - To retrieve all the objects along an inclusion with their schemas
        """
        read_fields = set(getattr(cls.Read, "__relationships__", set()))

        relationships = get_relationships_from_schema(schema=cls.Db)

        return {
            name: info for name, info in relationships.items() if name in read_fields
        }

    @classmethod
    def get_attributes(cls) -> set[str]:
        attributes = set()
        relationships = cls.get_relationships()

        # These are the fields according to the pydantic model
        fields = cls.Read.model_fields
        for field in fields:
            # If the field refers to a foreign key field we skip it as it'll be
            # included in get_relationships.
            if field in relationships:
                continue

            attributes.add(field)

        return attributes

    # TODO: Update to a type from sqlalchemy when we require 2.0
    def get_where(self) -> list[Any]:
        return []

    def get_joins(self) -> list[Any]:
        return []

    def get_options(self):
        options = []
        inclusions = self.inclusions or []

        # Build the query options based on the include
        for inclusion in inclusions:
            zipped_inclusion = self.zipped_inclusions_with_resource(
                inclusion=inclusion,
            )
            option = None

            for index, zipped_field in enumerate(zipped_inclusion):
                parent = zipped_inclusion[index - 1].resource.Db if index else self.Db
                attr = getattr(parent, zipped_field.field)

                if option:
                    option = option.joinedload(attr)
                else:
                    option = joinedload(attr)

            options.append(option)

        return options

    def get_select(self):
        options = self.get_options()
        select_stmt = select(self.Db)

        for join in self.get_joins():
            select_stmt = select_stmt.join(join)

        if options := self.get_options():
            select_stmt = select_stmt.options(*options)

        if where := self.get_where():
            select_stmt = select_stmt.where(*where)

        return select_stmt

    def get_count_select(self):
        select_stmt = select(func.count(self.Db.id))

        for join in self.get_joins():
            select_stmt = select_stmt.join(join)

        if where := self.get_where():
            select_stmt = select_stmt.where(*where)

        return select_stmt

    def get_object(
        self,
        id: int | str,
    ) -> types.TDb:
        select = self.get_select()

        id_field = getattr(self.Db, self.id_field or "id")

        try:
            return self.session.scalars(select.where(id_field == id)).unique().one()
        except sa_exceptions.NoResultFound:
            raise NotFound(f"{self.name} not found")

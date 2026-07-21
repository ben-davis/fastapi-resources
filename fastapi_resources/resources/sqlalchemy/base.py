import copy
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, Optional, Type

from sqlalchemy import ColumnExpressionArgument
from sqlalchemy import exc as sa_exceptions
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.associationproxy import (
    AssociationProxy,
    AssociationProxyExtensionType,
)
from sqlalchemy.orm import (
    MANYTOONE,
    ONETOMANY,
    DeclarativeBase,
    Mapper,
    RelationshipDirection,
    Session,
    joinedload,
)

from fastapi_resources.resources import base_resource
from fastapi_resources.resources.sqlalchemy.exceptions import NotFound

from . import types


@dataclass
class SAInstrumentedRelationship:
    direction: RelationshipDirection
    update_field: str
    many: bool
    related_schema: Type[DeclarativeBase]
    loaded_field: str | None = None


def get_instrumented_relationships_from_schema(inspected: Mapper[DeclarativeBase]):
    return {
        field: SAInstrumentedRelationship(
            related_schema=relationship.mapper.class_,
            many=relationship.uselist or False,
            direction=relationship.direction,
            update_field=list(
                relationship.remote_side
                if relationship.direction == ONETOMANY
                else relationship.local_columns
            )[0].name,
        )
        for field, relationship in inspected.relationships.items()
    }


def get_instrumented_relationships_from_schema_association_proxies(
    inspected: Mapper[DeclarativeBase],
):
    proxies: list[tuple[str, AssociationProxy]] = [
        (field, desc)
        for field, desc in inspected.all_orm_descriptors.items()
        if desc.extension_type is AssociationProxyExtensionType.ASSOCIATION_PROXY
    ]  # type: ignore

    sa_relationships: dict[str, SAInstrumentedRelationship] = {}

    for field, proxy in proxies:
        # This is the field on the model that the proxy proxies to
        target_collection = proxy.target_collection
        # This is the attribute on the target collection that gets pulled
        value_attr = proxy.value_attr

        # It can be any field type, but we only care about proxies to relationships
        target_collection_relationship = inspected.relationships.get(target_collection)
        if not target_collection_relationship:
            continue

        # The schema of the association table
        association_schema: type[
            DeclarativeBase
        ] = target_collection_relationship.mapper.class_
        association_inspected = inspect(association_schema)
        # The relationship on the association that we're extracting
        target_relationship = association_inspected.relationships[value_attr]

        sa_relationships[field] = SAInstrumentedRelationship(
            related_schema=target_relationship.mapper.class_,
            # We want to use the `many` based on the field we're proxing to
            many=target_collection_relationship.uselist or False,
            # Same with the direction
            direction=target_collection_relationship.direction,
            # The update_field isn't supported for associations, at least right now
            # update_field="",
            update_field=list(
                target_relationship.remote_side
                if target_relationship.direction == ONETOMANY
                else target_relationship.local_columns
            )[0].name,
            # We can't load from the association proxy, instead we load from the
            # field the proxy uses
            loaded_field=target_collection,
        )

    return sa_relationships


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
    inspected = inspect(schema)

    # Just a sanity check. This function should never be called for a relationship
    # that already exists.
    assert (parent_key, schema) not in schema_cache
    schema_cache[(parent_key, schema)] = parent_schema_with_relationships

    # Get relationships from actual relationships()
    sa_relationships = get_instrumented_relationships_from_schema(inspected=inspected)
    # Get relationships via AssociationProxies
    sa_relationships.update(
        get_instrumented_relationships_from_schema_association_proxies(
            inspected=inspected
        )
    )

    # Build SQLAlchemyRelationshipInfo objects from the instrumented relationships
    for field, sqlalchemy_relationship in sa_relationships.items():
        related_schema = sqlalchemy_relationship.related_schema
        many = sqlalchemy_relationship.many

        # Used to uniquely identify the related schema relative to a parent
        new_parent_key = f"{schema}.{field}"

        # TODO: Handle MANYTOMANY
        direction = sqlalchemy_relationship.direction
        update_field = sqlalchemy_relationship.update_field

        # If this branch already contains the schema with the same parent,
        # we can reuse the relationship to avoid a cycle.
        if relationship_info := schema_cache.get((new_parent_key, related_schema)):
            relationships[field] = types.SQLAlchemyRelationshipInfo(
                schema_with_relationships=relationship_info,
                many=many,
                field=field,
                direction=direction,
                update_field=update_field,
                loaded_field=sqlalchemy_relationship.loaded_field,
            )
            continue

        # For any relationship, the child will have a backpopulated reference
        # to the parent; we want to exclude that from available relationships
        if field == immediate_parent_backpopulated_field:
            continue

        # TODO: Can we cache the relationships when added to the registry?
        # NOTE: If there's no relationship on the schema, that means this is a
        # simulated relationship via an AssociationProxy. Those don't have
        # backpopulated fields, so we can safely set this to "".
        backpopulated_field = (
            inspected.relationships[field].back_populates
            if field in inspected.relationships
            else ""
        )

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
            loaded_field=sqlalchemy_relationship.loaded_field,
        )

    return relationships


class BaseSQLAlchemyResource(
    base_resource.Resource[types.TDb],
    types.SQLAlchemyResourceProtocol[types.TDb],
    Generic[types.TDb],
):
    registry: dict[Type[DeclarativeBase], type["BaseSQLAlchemyResource"]] = {}

    Repo: ClassVar[Optional[type]]  # set on subclass or by factory
    commands: ClassVar[Optional[Any]] = None  # set on subclass or by factory

    Paginator: ClassVar[Optional[Type[types.PaginatorProtocol]]]
    paginator: Optional[types.PaginatorProtocol]

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
        messagebus_handle=None,
        *args,
        **kwargs,
    ):
        self.messagebus_handle = messagebus_handle or (lambda cmd: None)

        Repo = getattr(self, "Repo", None)
        context = kwargs.get("context") or {}
        id_field = getattr(self, "id_field", None)
        if Repo is not None and session is not None:
            self.repo = Repo(session=session, context=context, id_field=id_field)
        elif Repo is not None:
            # No session — repo won't be usable; allow for testing without DB
            self.repo = None
        else:
            # Legacy path: no Repo defined, store session directly for old tests
            self.session = session

        if Paginator := getattr(self, "Paginator", None):
            self.paginator = Paginator(cursor=cursor, limit=limit)

        super().__init__(inclusions=inclusions, *args, **kwargs)

    def close(self):
        if repo := getattr(self, "repo", None):
            if repo and hasattr(repo, "session"):
                repo.session.close()
        elif session := getattr(self, "session", None):
            session.close()

    def generate_id(self):
        import uuid
        return uuid.uuid4()

    def get_options(self):
        """Build SQLAlchemy joinedload options from current inclusions.

        Called by list/retrieve to pass eager-loading options to the repo.
        Kept on the resource because it needs the registry to resolve resource classes.
        """
        options = []
        inclusions = self.inclusions or []

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

    @classmethod
    def get_relationships(cls) -> types.Relationships:
        read_fields = set(getattr(cls.Read, "__relationships__", set()))
        relationships = get_relationships_from_schema(schema=cls.Db)
        return {
            name: info for name, info in relationships.items() if name in read_fields
        }

    @classmethod
    def get_attributes(cls) -> set[str]:
        attributes = set()
        relationships = cls.get_relationships()
        fields = cls.Read.model_fields
        for field in fields:
            if field in relationships:
                continue
            attributes.add(field)
        return attributes

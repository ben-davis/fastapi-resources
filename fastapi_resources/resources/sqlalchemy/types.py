from dataclasses import dataclass
from typing import ClassVar, Generic, Optional, Protocol, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, RelationshipDirection, Session

from fastapi_resources.resources import types

Inclusions = types.Inclusions


class PaginatorProtocol(Protocol):
    def __init__(self, cursor: Optional[str] = None, limit: Optional[int] = None):
        ...

    def paginate_select(self, select: Select) -> Select:
        ...

    def get_next(self, count: int) -> Optional[str]:
        ...


@dataclass()
class SchemaWithRelationships:
    schema: Type[DeclarativeBase]
    relationships: "Relationships"


@dataclass
class SQLAlchemyRelationshipInfo:
    schema_with_relationships: SchemaWithRelationships
    many: bool
    field: str
    direction: RelationshipDirection
    update_field: str


Relationships = dict[str, SQLAlchemyRelationshipInfo]


TDb = TypeVar("TDb", bound=DeclarativeBase)


class SQLAlchemyResourceProtocol(types.ResourceProtocol, Protocol, Generic[TDb]):
    Db: ClassVar[Type[TDb]]
    Read: ClassVar[Type[BaseModel]]
    Create: ClassVar[Optional[Type[BaseModel]]] = None
    Update: ClassVar[Optional[Type[BaseModel]]] = None

    engine: ClassVar[Optional[Engine]] = None

    session: Session

    registry: ClassVar[
        dict[Type[DeclarativeBase], type["SQLAlchemyResourceProtocol"]]
    ] = {}

    Paginator: Optional[PaginatorProtocol]

    @classmethod
    def get_relationships(
        cls,
    ) -> dict[str, SQLAlchemyRelationshipInfo]:
        """Get the relationships for the resource."""
        ...

    @classmethod
    def get_attributes(cls) -> set[str]:
        """Get the non-relationships attributes for the resource.

        The attributes that end up in the response depend on those specified in
        the Read schema; it'll be a subset of those returned here.
        """
        ...

    def get_related(self, obj: DeclarativeBase, inclusion: list[str]) -> list[TDb]:
        ...

    def get_object(self, id: int | str) -> TDb:
        ...

    def get_select(self) -> Select[TDb]:
        ...

    def get_where(self) -> list[str]:
        ...

    def get_count_select(self) -> Select[TDb]:
        ...


@dataclass
class SelectedObj:
    obj: DeclarativeBase
    resource: "SQLAlchemyResourceProtocol"

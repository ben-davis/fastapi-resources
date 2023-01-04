from dataclasses import dataclass
from typing import ClassVar, Generic, Optional, Protocol, Type, TypeVar

from sqlalchemy.engine import Engine
from sqlalchemy.orm import MANYTOMANY, ONETOMANY
from sqlmodel import Session, SQLModel
from sqlmodel.sql.expression import SelectOfScalar

from fastapi_resources.resources import types

Inclusions = types.Inclusions


class PaginatorProtocol(Protocol):
    def __init__(self, cursor: Optional[str] = None, limit: Optional[int] = None):
        ...

    def paginate_select(self, select: SelectOfScalar) -> SelectOfScalar:
        ...

    def get_next(self, count: int) -> Optional[str]:
        ...


@dataclass()
class SchemaWithRelationships:
    schema: Type[SQLModel]
    relationships: "Relationships"


@dataclass
class SQLModelRelationshipInfo:
    schema_with_relationships: SchemaWithRelationships
    many: bool
    field: str
    direction: ONETOMANY | MANYTOMANY
    update_field: str


Relationships = dict[str, SQLModelRelationshipInfo]


TDb = TypeVar("TDb", bound=SQLModel)


class SQLResourceProtocol(types.ResourceProtocol, Protocol, Generic[TDb]):
    Db: ClassVar[Type[TDb]]
    Read: ClassVar[Type[SQLModel]]
    Create: ClassVar[Optional[Type[SQLModel]]] = None
    Update: ClassVar[Optional[Type[SQLModel]]] = None

    engine: ClassVar[Optional[Engine]] = None

    session: Session

    registry: dict[Type[SQLModel], type["SQLResourceProtocol"]] = {}

    Paginator: Optional[PaginatorProtocol]

    @classmethod
    def get_relationships(
        cls,
    ) -> dict[str, SQLModelRelationshipInfo]:
        """Get the relationships for the resource."""
        ...

    @classmethod
    def get_attributes(cls) -> set[str]:
        """Get the non-relationships attributes for the resource.

        The attributes that end up in the response depend on those specified in
        the Read schema; it'll be a subset of those returned here.
        """
        ...

    def get_related(self, obj: SQLModel, inclusion: list[str]) -> list[TDb]:
        ...

    def get_object(self, id: int | str) -> TDb:
        ...

    def get_select(self) -> SelectOfScalar[TDb]:
        ...

    def get_where(self) -> list[str]:
        ...

    def get_count_select(self) -> SelectOfScalar[TDb]:
        ...


@dataclass
class SelectedObj:
    obj: SQLModel
    resource: "SQLResourceProtocol"

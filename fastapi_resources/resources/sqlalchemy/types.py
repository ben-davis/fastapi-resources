from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Generic, Literal, Optional, Protocol, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, RelationshipDirection, Session

from fastapi_resources.resources import types

Inclusions = types.Inclusions


class PaginatorProtocol(Protocol):
    def __init__(self, cursor: Optional[str] = None, limit: Optional[int] = None):
        ...

    def paginate_select(self, select) -> Any:
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
    loaded_field: str | None = None


Relationships = dict[str, SQLAlchemyRelationshipInfo]


TDb = TypeVar("TDb", bound=DeclarativeBase)

Method = (
    Literal["retrieve"]
    | Literal["list"]
    | Literal["delete"]
    | Literal["delete_all"]
    | Literal["update"]
    | Literal["create"]
)


class SQLAlchemyResourceProtocol(types.ResourceProtocol, Protocol, Generic[TDb]):
    Db: ClassVar[Type[TDb]]
    Read: ClassVar[Type[BaseModel]]
    Create: ClassVar[Optional[Type[BaseModel]]] = None
    Update: ClassVar[Optional[Type[BaseModel]]] = None
    commands: ClassVar[Optional[Any]] = None

    registry: ClassVar[
        dict[Type[DeclarativeBase], type["SQLAlchemyResourceProtocol"]]
    ] = {}

    repo: Any
    messagebus_handle: Callable[..., Any]

    Paginator: Optional[PaginatorProtocol]

    @classmethod
    def get_relationships(cls) -> dict[str, SQLAlchemyRelationshipInfo]:
        ...

    @classmethod
    def get_attributes(cls) -> set[str]:
        ...

    def get_related(self, obj: DeclarativeBase, inclusion: list[str]) -> list[TDb]:
        ...

    def get_options(self) -> list:
        ...

    def generate_id(self) -> Any:
        ...


@dataclass
class SelectedObj:
    obj: DeclarativeBase
    resource: "SQLAlchemyResourceProtocol"

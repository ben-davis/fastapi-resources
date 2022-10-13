from dataclasses import dataclass
from typing import (
    Callable,
    ClassVar,
    Generic,
    List,
    Optional,
    Protocol,
    Set,
    Type,
    TypeVar,
)

from pydantic import BaseModel

Inclusions = list[list[str]]


TDb = TypeVar("TDb", bound=BaseModel)
TBaseModel = TypeVar("TBaseModel", bound=BaseModel)


@dataclass
class SchemaWithRelationships:
    schema: Type[BaseModel]
    relationships: "Relationships"


@dataclass
class RelationshipInfo:
    schema_with_relationships: SchemaWithRelationships
    many: bool
    field: str


Relationships = dict[str, RelationshipInfo]


@dataclass
class SelectedObj:
    obj: BaseModel
    resource: "ResourceProtocol"


class ResourceProtocol(Protocol, Generic[TDb, TBaseModel]):
    name: ClassVar[str]
    plural_name: ClassVar[str]

    Db: ClassVar[Type[TDb]]
    Read: ClassVar[Type[TBaseModel]]

    Create: ClassVar[Optional[Type[TBaseModel]]]
    Update: ClassVar[Optional[Type[TBaseModel]]]

    create: ClassVar[Optional[Callable]] = None
    list: ClassVar[Optional[Callable]] = None
    update: ClassVar[Optional[Callable]] = None
    delete: ClassVar[Optional[Callable]] = None
    retrieve: ClassVar[Optional[Callable]] = None

    inclusions: Inclusions
    context: dict = {}

    def __init__(*args, **kwargs):
        pass

    @classmethod
    def get_relationships(
        cls,
    ) -> dict[str, RelationshipInfo]:
        ...

    @classmethod
    def get_attributes(cls) -> Set[str]:
        """Get the non-relationships attributes for the resource.

        The attributes that end up in the response depend on those specified in
        the Read schema; it'll be a subset of those returned here.
        """
        ...

    def get_related(self, obj: BaseModel, inclusion: List[str]) -> List[SelectedObj]:
        ...

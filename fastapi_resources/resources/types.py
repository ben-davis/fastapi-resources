from typing import Callable, ClassVar, List, Optional, Protocol, Set, Type

from fastapi import Request
from pydantic.main import BaseModel


class RelationshipProtocol(Protocol):
    schema: Type[BaseModel]
    many: bool


Inclusions = list[list[str]]


class ResourceProtocol(Protocol):
    name: ClassVar[str]
    plural_name: ClassVar[str]

    Db: ClassVar[Type[BaseModel]]
    Read: ClassVar[Type[BaseModel]]

    Create: ClassVar[Optional[Type[BaseModel]]]
    Update: ClassVar[Optional[Type[BaseModel]]]

    create: Optional[Callable]
    list: Optional[Callable]
    update: Optional[Callable]
    delete: Optional[Callable]
    retrieve: Optional[Callable]

    request: Request
    inclusions: Inclusions

    @classmethod
    def get_relationships(
        cls,
    ) -> dict[str, RelationshipProtocol]:
        ...

    @classmethod
    def get_attributes(cls) -> Set[str]:
        """Get the non-relationships attributes for the resource.

        The attributes that end up in the response depend on those specified in
        the Read schema; it'll be a subset of those returned here.
        """
        ...

    def get_related(self, obj: BaseModel, inclusion: List[str]) -> List[BaseModel]:
        ...

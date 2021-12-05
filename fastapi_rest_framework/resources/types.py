from typing import Callable, ClassVar, Optional, Protocol, Type

from fastapi import Request
from pydantic.main import BaseModel


class RelationshipProtocol(Protocol):
    schema: Type[BaseModel]
    many: bool


Inclusions = list[list[str]]


class ResourceProtocol(Protocol):
    name: ClassVar[str]

    relationships: ClassVar[dict[str, RelationshipProtocol]]

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

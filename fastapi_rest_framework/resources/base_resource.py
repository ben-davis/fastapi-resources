import dataclasses
from typing import Callable, ClassVar, Optional, Type

from fastapi import Request
from pydantic.main import BaseModel

from .types import Inclusions


@dataclasses.dataclass
class Relationship:
    schema: Type[BaseModel]
    many: bool


class Resource:
    name: ClassVar[str]

    relationships: ClassVar[dict[str, Relationship]]

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

    def __init__(self, request: Request, inclusions: Optional[Inclusions] = None):
        self.request = request
        self.inclusions = inclusions or []

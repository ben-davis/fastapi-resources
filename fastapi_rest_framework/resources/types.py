from typing import Callable, ClassVar, List, Optional, Protocol, Type, Union

from fastapi import Request
from pydantic.main import BaseModel


class RelationshipProtocol(Protocol):
    schema: Type[BaseModel]
    many: bool


Inclusions = list[list[str]]


class GetRelationships(Protocol):
    def __call__(
        self,
    ) -> List[RelationshipProtocol]:
        ...


class GetRelated(Protocol):
    def __call__(
        self,
        obj: BaseModel,
        field: str,
    ) -> Union[List[BaseModel], BaseModel]:
        ...


class ResourceProtocol(Protocol):
    name: ClassVar[str]

    Db: ClassVar[Type[BaseModel]]
    Read: ClassVar[Type[BaseModel]]

    Create: ClassVar[Optional[Type[BaseModel]]]
    Update: ClassVar[Optional[Type[BaseModel]]]

    create: Optional[Callable]
    list: Optional[Callable]
    update: Optional[Callable]
    delete: Optional[Callable]
    retrieve: Optional[Callable]

    get_relationships: GetRelationships
    get_related: GetRelated

    request: Request
    inclusions: Inclusions

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel
from pydantic.generics import GenericModel


class Object(BaseModel):
    id: str


TRead = TypeVar("TRead", bound=Object)
TName = TypeVar("TName", bound=str)
TUpdate = TypeVar("TUpdate", bound=Object)
TCreate = TypeVar("TCreate", bound=Object)
TAttributes = TypeVar("TAttributes")
TRelationships = TypeVar("TRelationships")
TIncluded = TypeVar("TIncluded")
TType = TypeVar("TType", bound=str)


class TIncludeParam(str):
    pass


class JALinks(BaseModel):
    """A links-object"""

    self: Optional[str] = ""
    # Will be used when relationship endpoints are implemented
    related: Optional[str] = ""


class JAResourceIdentifierObject(GenericModel, Generic[TType]):
    type: TType
    id: str


class JARelationshipsObjectSingle(GenericModel, Generic[TType]):
    links: Optional[JALinks]
    data: Optional[JAResourceIdentifierObject[TType]] = None


class JARelationshipsObjectMany(GenericModel, Generic[TType]):
    links: Optional[JALinks]
    data: list[JAResourceIdentifierObject[TType]]


class JAResourceObject(GenericModel, Generic[TAttributes, TRelationships, TName]):
    id: str
    type: TName
    attributes: TAttributes
    links: JALinks
    relationships: TRelationships


class JAUpdateObject(GenericModel, Generic[TAttributes, TRelationships, TName]):
    id: str
    type: TName
    attributes: Optional[TAttributes]
    relationships: Optional[TRelationships]


class JAUpdateRequest(GenericModel, Generic[TAttributes, TRelationships, TName]):
    data: JAUpdateObject[TAttributes, TRelationships, TName]


class JACreateObject(GenericModel, Generic[TAttributes, TRelationships, TName]):
    type: TName
    attributes: Optional[TAttributes]
    relationships: Optional[TRelationships]


class JACreateRequest(GenericModel, Generic[TAttributes, TRelationships, TName]):
    data: JACreateObject[TAttributes, TRelationships, TName]


class JAResponseSingle(
    GenericModel, Generic[TAttributes, TRelationships, TName, TIncluded]
):
    data: JAResourceObject[TAttributes, TRelationships, TName]
    included: TIncluded
    links: JALinks


class JAResponseList(
    GenericModel, Generic[TAttributes, TRelationships, TName, TIncluded]
):
    data: List[JAResourceObject[TAttributes, TRelationships, TName]]
    included: TIncluded
    links: JALinks

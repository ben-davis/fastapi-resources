from typing import Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel


class Object(BaseModel):
    id: str


TRead = TypeVar("TRead", bound=Object)
TName = TypeVar("TName", bound=str)
TUpdate = TypeVar("TUpdate", bound=Object)
TCreate = TypeVar("TCreate", bound=Object)
TAttributes = TypeVar("TAttributes")
TRelationships = TypeVar("TRelationships")
TIncluded = TypeVar("TIncluded")
TMeta = TypeVar("TMeta")
TType = TypeVar("TType", bound=str)


class TIncludeParam(str):
    pass


class JALinks(BaseModel):
    """A links-object"""

    self: Optional[str] = ""


class JALinksWithPagination(JALinks):
    next: Optional[str] = None


TLinks = TypeVar("TLinks", bound=Union[JALinks, JALinksWithPagination])


class JAResourceIdentifierObject(BaseModel, Generic[TType]):
    type: TType
    id: str


class JARelationshipsObjectSingle(BaseModel, Generic[TType]):
    links: Optional[JALinks] = None
    data: Optional[JAResourceIdentifierObject[TType]] = None


class JARelationshipsObjectMany(BaseModel, Generic[TType]):
    links: Optional[JALinks] = None
    data: list[JAResourceIdentifierObject[TType]]


class JAResourceObject(BaseModel, Generic[TAttributes, TRelationships, TName]):
    id: str
    type: TName
    attributes: TAttributes
    links: JALinks
    relationships: TRelationships


class JAUpdateObject(BaseModel, Generic[TAttributes, TRelationships, TName]):
    id: str
    type: TName
    attributes: Optional[TAttributes] = None
    relationships: Optional[TRelationships] = None


class JAUpdateRequest(BaseModel, Generic[TAttributes, TRelationships, TName]):
    data: JAUpdateObject[TAttributes, TRelationships, TName]


class JACreateObject(BaseModel, Generic[TAttributes, TRelationships, TName]):
    type: TName
    attributes: Optional[TAttributes] = None
    relationships: Optional[TRelationships] = None


class JACreateRequest(BaseModel, Generic[TAttributes, TRelationships, TName]):
    data: JACreateObject[TAttributes, TRelationships, TName]


class JAResponseSingle(
    BaseModel, Generic[TAttributes, TRelationships, TName, TIncluded]
):
    data: JAResourceObject[TAttributes, TRelationships, TName]
    included: TIncluded
    links: JALinks


class JAResponseList(
    BaseModel,
    Generic[TAttributes, TRelationships, TName, TIncluded, TMeta, TLinks],
):
    data: List[JAResourceObject[TAttributes, TRelationships, TName]]
    included: TIncluded
    links: TLinks
    meta: TMeta

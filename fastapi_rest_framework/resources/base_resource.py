import dataclasses
from typing import Optional, Type

from pydantic.main import BaseModel

from .types import Inclusions, RelationshipProtocol


@dataclasses.dataclass
class Relationship:
    schema: Type[BaseModel]
    many: bool


class Resource(RelationshipProtocol):
    def __init__(self, inclusions: Optional[Inclusions] = None, *args, **kwargs):
        self.inclusions = inclusions or []

    @classmethod
    def get_relationships(cls):
        return []

    def get_related(self, obj: BaseModel, field: str):
        raise NotImplementedError()

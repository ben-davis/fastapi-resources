from copy import copy
from dataclasses import dataclass
from typing import Optional, Type

from pydantic.main import BaseModel

from .types import Inclusions, RelationshipProtocol


@dataclass
class SchemaWithRelationships:
    schema: Type[BaseModel]
    relationships: "Relationships"


@dataclass
class SQLModelRelationshipInfo:
    schema_with_relationships: SchemaWithRelationships
    many: bool
    field: str


Relationships = dict[str, SQLModelRelationshipInfo]


def _validate(_relationships: Relationships, _inclusion: list[str]):
    if not _inclusion:
        return

    next_inclusions = copy(_inclusion)
    current_inclusion = next_inclusions.pop(0)

    relationship_info = _relationships.get(current_inclusion)
    assert relationship_info, f"Invalid inclusion {current_inclusion}"

    if next_relationships := relationship_info.schema_with_relationships.relationships:
        return _validate(
            _relationships=next_relationships,
            _inclusion=next_inclusions,
        )


class Resource(RelationshipProtocol):
    def __init__(self, inclusions: Optional[Inclusions] = None, *args, **kwargs):
        if inclusions:
            self.validate_inclusions(inclusions=inclusions)

        self.inclusions = inclusions or []

    def validate_inclusions(self, inclusions: Inclusions):
        """Validate the inclusions by walking the relationships."""
        relationships = self.get_relationships()

        for inclusion in inclusions:
            _validate(_relationships=relationships, _inclusion=inclusion)

    @classmethod
    def get_relationships(cls) -> Relationships:
        return {}

    def get_related(self, obj: BaseModel, inclusion: list[str]) -> list[BaseModel]:
        raise NotImplementedError()

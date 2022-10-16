from copy import copy
from dataclasses import dataclass
from typing import ClassVar, Generic, Optional, Type

from pydantic.main import BaseModel

from .types import Inclusions, Relationships, SelectedObj, TDb


@dataclass
class InclusionWithResource:
    field: str
    resource: type["Resource"]


class Resource(Generic[TDb]):
    # name: ClassVar[str]
    plural_name: ClassVar[Optional[str]]

    Db: ClassVar[Type[TDb]]
    registry: dict[Type[BaseModel], type["Resource"]] = {}

    def __init_subclass__(cls) -> None:
        if Db := getattr(cls, "Db", None):
            Resource.registry[Db] = cls

        # Pluralize name
        if name := getattr(cls, "name", None):
            cls.plural_name = getattr(cls, "plural_name", None) or f"{name}s"

        return super().__init_subclass__()

    def __init__(
        self,
        inclusions: Optional[Inclusions] = None,
        context: Optional[dict] = None,
        *args,
        **kwargs,
    ):
        if inclusions:
            self.validate_inclusions(inclusions=inclusions)

        self.inclusions = inclusions or []
        self.context = context or {}

    def close(self):
        pass

    def _zipped_inclusions_with_resource(
        self, _relationships: Relationships, _inclusion: list[str]
    ) -> list[InclusionWithResource]:
        if not _inclusion:
            return []

        next_inclusions = copy(_inclusion)
        current_inclusion = next_inclusions.pop(0)

        relationship_info = _relationships.get(current_inclusion)
        assert relationship_info, f"Invalid inclusion {current_inclusion}"

        if relationship_info.schema_with_relationships.schema not in self.registry:
            raise Exception(
                f"Resource not found for relationship {relationship_info.field}"
            )

        resource = self.registry[relationship_info.schema_with_relationships.schema]

        zipped_inclusions = [
            InclusionWithResource(field=current_inclusion, resource=resource)
        ]

        if (
            next_relationships := relationship_info.schema_with_relationships.relationships
        ):
            zipped_inclusions = [
                *zipped_inclusions,
                *self._zipped_inclusions_with_resource(
                    _relationships=next_relationships,
                    _inclusion=next_inclusions,
                ),
            ]

        return zipped_inclusions

    def validate_inclusions(self, inclusions: Inclusions):
        """Validate the inclusions by walking the relationships."""
        relationships = self.get_relationships()

        for inclusion in inclusions:
            self._zipped_inclusions_with_resource(
                _relationships=relationships, _inclusion=inclusion
            )

    def zipped_inclusions_with_resource(
        self, inclusion: list[str]
    ) -> list[InclusionWithResource]:
        return self._zipped_inclusions_with_resource(
            _relationships=self.get_relationships(),
            _inclusion=inclusion,
        )

    @classmethod
    def get_relationships(cls) -> Relationships:
        return {}

    @classmethod
    def get_attributes(cls) -> set[str]:
        return set(cls.Db.__fields__.keys())

    def get_related(self, obj: BaseModel, inclusion: list[str]) -> list[SelectedObj]:
        raise NotImplementedError()

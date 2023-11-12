from copy import copy
from dataclasses import dataclass
from typing import ClassVar, Generic, Optional, Type

from pydantic.main import BaseModel

from .types import Inclusions, Relationships, ResourceProtocol, SelectedObj, TDb


@dataclass
class InclusionWithResource:
    field: str
    resource: type["Resource"]


class Resource(ResourceProtocol, Generic[TDb]):
    # name: ClassVar[str]
    plural_name: ClassVar[Optional[str]]

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
        page: Optional[str] = None,
        limit: Optional[int] = None,
        *args,
        **kwargs,
    ):
        if inclusions:
            self.validate_inclusions(inclusions=inclusions)

        self.inclusions = inclusions or []
        self.context = context or {}
        self.tasks = []

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
        return set(cls.Read.model_fields.keys())

    def get_related(
        self,
        obj: TDb,
        inclusion: list[str],
    ) -> list[SelectedObj]:
        """Gets related objects based on an Inclusions path."""

        def select_objs(
            _obj, _inclusion: list[str], _relationships: Relationships
        ) -> list[SelectedObj]:
            next_inclusion = copy(_inclusion)
            field = next_inclusion.pop(0)
            relationship_info = _relationships[field]
            schema = relationship_info.schema_with_relationships.schema

            selected_objs = getattr(_obj, field)
            if not selected_objs:
                return []

            selected_objs = (
                selected_objs if isinstance(selected_objs, list) else [selected_objs]
            )

            selected_objs = [
                SelectedObj(obj=selected_obj, resource=Resource.registry[schema])
                for selected_obj in selected_objs
            ]

            if next_inclusion:
                selected_objs = [
                    *selected_objs,
                    *[
                        nested_obj
                        for selected_obj in selected_objs
                        for nested_obj in select_objs(
                            _obj=selected_obj.obj,
                            _inclusion=next_inclusion,
                            _relationships=relationship_info.schema_with_relationships.relationships,
                        )
                    ],
                ]

            return selected_objs

        return select_objs(
            _obj=obj, _inclusion=inclusion, _relationships=self.get_relationships()
        )

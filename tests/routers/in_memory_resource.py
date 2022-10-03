from copy import copy
from typing import Optional

from fastapi.exceptions import HTTPException
from fastapi_resources.resources import types
from fastapi_resources.resources.sqlmodel import (
    Relationships,
    SelectedObj,
    SQLModelResource,
)
from sqlmodel.main import SQLModel

id_counter = 1
test_db: dict[str, dict[int, SQLModel]] = {}


class InMemorySQLModelResource(SQLModelResource):
    def __init__(self, inclusions: Optional[types.Inclusions] = None, *args, **kwargs):
        self.inclusions = inclusions or []

    def get_object(self, id: int):
        obj = test_db[self.name].get(id)

        if not obj:
            raise HTTPException(status_code=404)

        return obj

    def get_related(self, obj: SQLModel, inclusion: list[str]):
        """Only supports to-one relationships."""

        def select_objs(
            _obj: SQLModel, _inclusion: list[str], _relationships: Relationships
        ) -> list[SelectedObj]:
            next_inclusion = copy(_inclusion)
            field = next_inclusion.pop(0)
            relationship_info = _relationships[field]
            schema = relationship_info.schema_with_relationships.schema
            related_resource = self.registry[schema]

            if relationship_info.many:
                related_resource_name = self.registry[schema].name

                selected_objs = [
                    SelectedObj(obj=related_obj, resource=related_resource)
                    for related_obj in test_db[related_resource_name].values()
                    if getattr(related_obj, f"{self.name}_id", "") == obj.id
                ]
                print(selected_objs)
            else:
                # Assumes the related object is just the field with _id suffix
                related_id = getattr(_obj, f"{field}_id", None)
                if not related_id:
                    return []

                selected_obj = test_db[field][related_id]
                selected_objs = [
                    SelectedObj(obj=selected_obj, resource=related_resource)
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

    def create(self, model: SQLModel):
        global id_counter

        obj = self.Db.from_orm(model)
        obj.id = id_counter
        test_db[self.name][id_counter] = obj
        id_counter += 1

        return obj

    def list(self):
        return list(test_db[self.name].values())

    def retrieve(self, id: int):
        return self.get_object(id=id)

    def update(self, id: int, model: SQLModel):
        obj = self.get_object(id=id)

        data = model.dict(exclude_unset=True)
        for key, value in data.items():
            setattr(obj, key, value)

        return obj

    def delete(self, id: int):
        self.get_object(id=id)

        del test_db[self.name][id]

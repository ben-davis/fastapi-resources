from copy import copy
from typing import Optional

from fastapi.exceptions import HTTPException
from sqlmodel.main import SQLModel

from fastapi_rest_framework.resources import types
from fastapi_rest_framework.resources.sqlmodel import SelectedObj, SQLModelResource

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

        def select_inclusion(obj: SQLModel, inclusion: list[str]) -> list[SelectedObj]:
            next_inclusion = copy(inclusion)
            field = next_inclusion.pop(0)

            # Assumes the related object is just the field with _id suffix
            related_id = getattr(obj, f"{field}_id")
            if not related_id:
                return []

            selected_obj = test_db[field][related_id]
            resource = self.registry[type(selected_obj)]
            selected_objs = [SelectedObj(obj=selected_obj, resource=resource)]

            if next_inclusion:
                selected_objs = [
                    selected_obj,
                    *[
                        nested_obj
                        for nested_obj in select_inclusion(
                            obj=selected_obj, inclusion=next_inclusion
                        )
                    ],
                ]

            return selected_objs

        return select_inclusion(obj=obj, inclusion=inclusion)

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

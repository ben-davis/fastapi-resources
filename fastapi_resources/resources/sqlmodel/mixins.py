from typing import Optional

from sqlalchemy.orm import MANYTOONE, ONETOMANY
from sqlmodel import select, update

from fastapi_resources.resources.sqlmodel import types
from fastapi_resources.resources.sqlmodel.exceptions import NotFound


class CreateResourceMixin:
    def create(
        self: types.SQLResourceProtocol[types.TDb],
        attributes: dict,
        relationships: Optional[dict[str, str | int | list[str | int]]] = None,
        **kwargs,
    ):
        row = self.Db(**attributes)

        for key, value in kwargs.items():
            setattr(row, key, value)

        relationships = relationships or {}
        model_relationships = self.get_relationships()
        did_set_relationship = False

        for field, related_ids in relationships.items():
            relationship = model_relationships[field]
            direction = relationship.direction

            RelatedResource = self.registry[
                relationship.schema_with_relationships.schema
            ]
            related_db_model = RelatedResource.Db
            new_related_ids = (
                related_ids if isinstance(related_ids, list) else [related_ids]
            )

            # Do a select to check we have permission
            related_resource = RelatedResource(context=self.context)

            if related_where := related_resource.get_where():
                results = self.session.exec(
                    select(related_db_model).where(
                        related_db_model.id.in_(new_related_ids), *related_where
                    )
                ).all()

                if len(results) != len(new_related_ids):
                    raise NotFound()

            if direction == MANYTOONE:
                # Can update locally via a setattr
                setattr(row, relationship.update_field, new_related_ids[0])
                did_set_relationship = True

        self.session.add(row)
        self.session.commit()

        # Update many relationships that require a separate update on the relationship table
        for field, related_ids in relationships.items():
            relationship = model_relationships[field]
            direction = relationship.direction

            if direction != ONETOMANY:
                continue

            assert isinstance(
                related_ids, list
            ), "A list of IDs must be provided for {field}"

            RelatedResource = self.registry[
                relationship.schema_with_relationships.schema
            ]
            related_db_model = RelatedResource.Db
            related_resource = RelatedResource(context=self.context)
            related_where = related_resource.get_where()

            # Update the related objects
            self.session.execute(
                update(related_db_model)
                .where(related_db_model.id.in_(related_ids), *related_where)
                .values({relationship.update_field: row.id})
            )

            did_set_relationship = True

        if did_set_relationship:
            self.session.refresh(row)

        return row


class UpdateResourceMixin:
    def update(
        self: types.SQLResourceProtocol[types.TDb],
        *,
        id: int | str,
        attributes: dict,
        relationships: Optional[dict[str, str | int | list[str | int]]] = None,
        **kwargs,
    ):
        row = self.get_object(id=id)

        for key, value in list(attributes.items()) + list(kwargs.items()):
            setattr(row, key, value)

        model_relationships = self.get_relationships()

        if relationships:
            for field, related_ids in relationships.items():
                relationship = model_relationships[field]
                direction = relationship.direction

                RelatedResource = self.registry[
                    relationship.schema_with_relationships.schema
                ]
                related_db_model = RelatedResource.Db
                new_related_ids = (
                    related_ids if isinstance(related_ids, list) else [related_ids]
                )

                # Do a select to check we have permission
                related_resource = RelatedResource(context=self.context)

                if related_where := related_resource.get_where():
                    results = self.session.exec(
                        select(related_db_model).where(
                            related_db_model.id.in_(new_related_ids), *related_where
                        )
                    ).all()

                    if len(results) != len(new_related_ids):
                        raise NotFound(f"{related_resource.name} not found")

                if direction == ONETOMANY:
                    assert isinstance(
                        related_ids, list
                    ), "A list of IDs must be provided for {field}"

                    # Update the related objects
                    self.session.execute(
                        update(related_db_model)
                        .where(related_db_model.id.in_(new_related_ids))
                        .values({relationship.update_field: id})
                    )

                    # Detach the old related objects
                    # NOTE: This will raise if the foreign key is required. Is this OK?
                    self.session.execute(
                        update(related_db_model)
                        .where(
                            getattr(related_db_model, relationship.update_field) == id,
                            related_db_model.id.not_in(new_related_ids),
                        )
                        .values({relationship.update_field: None})
                    )

                elif direction == MANYTOONE:
                    # Can update locally via a setattr
                    setattr(row, relationship.update_field, related_ids)

        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        return row


class ListResourceMixin:
    def list(self: types.SQLResourceProtocol[types.TDb]):
        select = self.get_select()

        rows = self.session.exec(select).unique().all()

        return rows


class RetrieveResourceMixin:
    def retrieve(self: types.SQLResourceProtocol[types.TDb], *, id: int | str):
        row = self.get_object(id=id)

        return row


class DeleteResourceMixin:
    def delete(self: types.SQLResourceProtocol[types.TDb], *, id: int | str):
        row = self.get_object(id=id)

        self.session.delete(row)
        self.session.commit()

        return {"ok": True}

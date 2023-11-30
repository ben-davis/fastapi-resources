from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.orm import MANYTOONE, ONETOMANY

from fastapi_resources.resources.sqlalchemy import types
from fastapi_resources.resources.sqlalchemy.exceptions import NotFound


class CreateResourceMixin:
    def create(
        self: types.SQLAlchemyResourceProtocol[types.TDb],
        attributes: dict,
        relationships: Optional[dict[str, str | int | list[str | int]]] = None,
        **kwargs,
    ):
        create_kwargs = attributes | kwargs
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

            related_resource = RelatedResource(context=self.context)

            where = [related_db_model.id.in_(new_related_ids)]

            # Use the resource's where clause so that if it adds permissions, those
            # are automatically used when setting the relationship.
            if related_where := related_resource.get_where():
                where += related_where

            # Do a select to check we have permission, and so we can set the
            # relationship using the full object (required to support dataclasses).
            results = self.session.scalars(select(related_db_model).where(*where)).all()

            if len(results) != len(new_related_ids):
                raise NotFound()

            if direction == MANYTOONE:
                # Can update locally via a setattr, using the field name and the resolved
                # object.
                create_kwargs[field] = results[0]
                did_set_relationship = True

        row = self.Db(**create_kwargs)
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
        self: types.SQLAlchemyResourceProtocol[types.TDb],
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
                    results = self.session.scalars(
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
    def list(self: types.SQLAlchemyResourceProtocol[types.TDb]):
        select = self.get_select()

        paginator = getattr(self, "paginator", None)

        if paginator:
            select = paginator.paginate_select(select)

        rows = self.session.scalars(select).unique().all()
        count = self.session.scalars(self.get_count_select()).one()

        next = None

        if paginator:
            next = paginator.get_next(count=count)

        return rows, next, count


class RetrieveResourceMixin:
    def retrieve(self: types.SQLAlchemyResourceProtocol[types.TDb], *, id: int | str):
        row = self.get_object(id=id)

        return row


class DeleteResourceMixin:
    def delete(self: types.SQLAlchemyResourceProtocol[types.TDb], *, id: int | str):
        row = self.get_object(id=id)

        self.session.delete(row)
        self.session.commit()

        return {"ok": True}

    def delete_all(self: types.SQLAlchemyResourceProtocol[types.TDb]):
        where = self.get_where()

        self.session.execute(delete(self.Db).where(*where))
        self.session.commit()

        return [], None, 0

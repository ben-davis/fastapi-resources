from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import MANYTOONE

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
        model_relationships = self.relationships

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

            # Do a select to check we have permission, and so we can set the
            # relationship using the full object (required to support dataclasses).
            results = self.session.scalars(
                # Use the resource's get_select() so that if it adds permissions, those
                # are automatically used when setting the relationship.
                related_resource.get_select(method="create").where(
                    related_db_model.id.in_(new_related_ids),
                )
            ).all()

            if len(results) != len(new_related_ids):
                raise NotFound()

            if direction == MANYTOONE:
                results = results[0]

            # Can update locally via a setattr, using the field name and the resolved
            # object.
            create_kwargs[field] = results

        row = self.Db(**create_kwargs)
        self.session.add(row)
        self.session.commit()

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
        row = self.get_object(id=id, method="update")

        for key, value in list(attributes.items()) + list(kwargs.items()):
            setattr(row, key, value)

        model_relationships = self.relationships

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
                results = self.session.scalars(
                    related_resource.get_select(method="update").where(
                        related_db_model.id.in_(new_related_ids),
                    )
                ).all()

                if len(results) != len(new_related_ids):
                    raise NotFound(f"{related_resource.name} not found")

                if direction == MANYTOONE:
                    results = results[0]

                setattr(row, relationship.field, results)

        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        return row


class ListResourceMixin:
    def list(self: types.SQLAlchemyResourceProtocol[types.TDb]):
        select = self.get_select(method="list")

        paginator = getattr(self, "paginator", None)

        if paginator:
            select = paginator.paginate_select(select)

        rows = self.session.scalars(select).unique().all()
        count = self.session.scalars(self.get_count_select(method="list")).one()

        next = None

        if paginator:
            next = paginator.get_next(count=count)

        return rows, next, count


class RetrieveResourceMixin:
    def retrieve(self: types.SQLAlchemyResourceProtocol[types.TDb], *, id: int | str):
        row = self.get_object(id=id, method="retrieve")

        return row


class DeleteResourceMixin:
    def delete(self: types.SQLAlchemyResourceProtocol[types.TDb], *, id: int | str):
        row = self.get_object(id=id, method="delete")

        self.session.delete(row)
        self.session.commit()

        return {"ok": True}


class DeleteAllResourceMixin:
    def delete_all(self: types.SQLAlchemyResourceProtocol[types.TDb]):
        where = self.get_where(method="delete_all")

        self.session.execute(delete(self.Db).where(*where))
        self.session.commit()

        return [], None, 0

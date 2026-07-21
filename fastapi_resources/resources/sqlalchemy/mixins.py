import dataclasses
from typing import Optional

from sqlalchemy import delete

from fastapi_resources.resources.sqlalchemy import types
from fastapi_resources.resources.sqlalchemy.exceptions import NotFound


class CreateResourceMixin:
    def create(
        self: types.SQLAlchemyResourceProtocol[types.TDb],
        attributes: dict,
        relationships: Optional[dict] = None,
        **kwargs,
    ):
        relationships = relationships or {}
        cmd_kwargs = dict(attributes)
        cmd_kwargs.update(kwargs)

        # Map relationship field names → command field names (IDs)
        for field_name, rel_value in relationships.items():
            rel_info = self.relationships.get(field_name)
            if rel_info and not rel_info.many:
                cmd_kwargs[f"{field_name}_id"] = rel_value
            else:
                singular = field_name[:-1] if field_name.endswith("s") else field_name
                cmd_kwargs[f"{singular}_ids"] = (
                    rel_value if isinstance(rel_value, list) else [rel_value]
                )

        # Add a pre-generated ID if the command has an id field
        commands = getattr(self, "commands", None)
        if commands and hasattr(commands, "Create"):
            cmd_field_names = {f.name for f in dataclasses.fields(commands.Create)}
            if "id" in cmd_field_names:
                cmd_kwargs["id"] = self.generate_id()
            cmd = commands.Create(**cmd_kwargs)
        else:
            raise NotImplementedError(
                f"{type(self).__name__} has no commands.Create. "
                "Set commands on the resource or override create()."
            )

        created_id = self.messagebus_handle(cmd)
        return self.repo.get(created_id)


class UpdateResourceMixin:
    def update(
        self: types.SQLAlchemyResourceProtocol[types.TDb],
        *,
        id: int | str,
        attributes: dict,
        relationships: Optional[dict] = None,
        **kwargs,
    ):
        relationships = relationships or {}
        cmd_kwargs = {"id": id}
        cmd_kwargs.update(attributes)
        cmd_kwargs.update(kwargs)

        for field_name, rel_value in relationships.items():
            rel_info = self.relationships.get(field_name)
            if rel_info and not rel_info.many:
                cmd_kwargs[f"{field_name}_id"] = rel_value
            else:
                singular = field_name[:-1] if field_name.endswith("s") else field_name
                cmd_kwargs[f"{singular}_ids"] = (
                    rel_value if isinstance(rel_value, list) else [rel_value]
                )

        commands = getattr(self, "commands", None)
        if commands and hasattr(commands, "Update"):
            # Only pass fields the command actually declares
            valid = {f.name for f in dataclasses.fields(commands.Update)}
            cmd = commands.Update(**{k: v for k, v in cmd_kwargs.items() if k in valid})
        else:
            raise NotImplementedError(
                f"{type(self).__name__} has no commands.Update. "
                "Set commands on the resource or override update()."
            )

        updated_id = self.messagebus_handle(cmd)
        return self.repo.get(updated_id)


class ListResourceMixin:
    def list(self: types.SQLAlchemyResourceProtocol[types.TDb]):
        options = self.get_options()
        paginator = getattr(self, "paginator", None)
        return self.repo.list(options=options or None, paginator=paginator)


class RetrieveResourceMixin:
    def retrieve(self: types.SQLAlchemyResourceProtocol[types.TDb], *, id: int | str):
        options = self.get_options()
        return self.repo.get(id, options=options or None)


class DeleteResourceMixin:
    def delete(self: types.SQLAlchemyResourceProtocol[types.TDb], *, id: int | str):
        commands = getattr(self, "commands", None)
        if commands and hasattr(commands, "Delete"):
            self.messagebus_handle(commands.Delete(id=id))
        else:
            raise NotImplementedError(
                f"{type(self).__name__} has no commands.Delete. "
                "Set commands on the resource or override delete()."
            )
        return {"ok": True}


class DeleteAllResourceMixin:
    def delete_all(self: types.SQLAlchemyResourceProtocol[types.TDb]):
        self.repo.delete_all()
        return [], None, 0

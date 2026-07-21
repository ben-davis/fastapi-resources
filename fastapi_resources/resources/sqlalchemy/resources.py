from typing import Generic, Optional

from fastapi_resources.domain import build_commands
from fastapi_resources.repositories import build_sqlalchemy_repo

from . import base, mixins, types

__all__ = [
    "ListCreateResource",
    "ListCreateUpdateResource",
    "SQLAlchemyResource",
    "build_sqlalchemy_resource",
]


class ListCreateResource(
    mixins.CreateResourceMixin, mixins.ListResourceMixin, base.BaseSQLAlchemyResource
):
    pass


class ListCreateUpdateResource(
    mixins.ListResourceMixin,
    mixins.CreateResourceMixin,
    mixins.UpdateResourceMixin,
    base.BaseSQLAlchemyResource,
):
    pass


class SQLAlchemyResource(
    mixins.RetrieveResourceMixin,
    mixins.ListResourceMixin,
    mixins.CreateResourceMixin,
    mixins.UpdateResourceMixin,
    mixins.DeleteResourceMixin,
    base.BaseSQLAlchemyResource[types.TDb],
    types.SQLAlchemyResourceProtocol[types.TDb],
    Generic[types.TDb],
):
    pass


def build_sqlalchemy_resource(
    Db: type,
    Read,
    Create=None,
    Update=None,
    commands=None,
    Repo: Optional[type] = None,
):
    """Generate a full SQLAlchemy resource class (HTTP layer only).

    Generates commands and a repository if not provided. Does NOT register
    handlers with any bus — call bus.register_resource(commands, handlers) separately.
    """
    if Repo is None:
        Repo = build_sqlalchemy_repo(Db)

    if commands is None and (Create is not None or Update is not None):
        commands = build_commands(Db, Create=Create, Update=Update)

    attrs: dict = {"Db": Db, "Read": Read, "Repo": Repo, "commands": commands}
    if Create is not None:
        attrs["Create"] = Create
    if Update is not None:
        attrs["Update"] = Update

    return type(f"{Db.__name__}Resource", (SQLAlchemyResource,), attrs)

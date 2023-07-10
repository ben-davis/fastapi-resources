from typing import Generic

from . import base, mixins, types

__all__ = [
    "ListCreateResource",
    "ListCreateUpdateResource",
    "SQLAlchemyResource",
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

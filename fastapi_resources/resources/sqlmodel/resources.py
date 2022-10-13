from typing import Generic

from . import base, mixins, types

__all__ = [
    "ListCreateResource",
    "ListCreateUpdateResource",
    "SQLModelResource",
]


class ListCreateResource(
    mixins.CreateResourceMixin, mixins.ListResourceMixin, base.BaseSQLResource
):
    pass


class ListCreateUpdateResource(
    mixins.ListResourceMixin,
    mixins.CreateResourceMixin,
    mixins.UpdateResourceMixin,
    base.BaseSQLResource,
):
    pass


class SQLModelResource(
    mixins.RetrieveResourceMixin,
    mixins.ListResourceMixin,
    mixins.CreateResourceMixin,
    mixins.UpdateResourceMixin,
    mixins.DeleteResourceMixin,
    base.BaseSQLResource[types.TDb],
    types.SQLResourceProtocol[types.TDb],
    Generic[types.TDb],
):
    pass

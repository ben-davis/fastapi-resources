import functools
from typing import Callable, Literal

methods = Literal["post", "get", "patch", "delete"]


def action(detail: bool, methods: list[methods] = ["get"], **kwargs):
    def action_decorator(func: Callable):
        func.detail = detail
        func.methods = methods
        func.kwargs = kwargs

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            self = args[0]
            request = kwargs["request"]
            resource = self.get_resource(request=request)

            rows = func(*args, **kwargs)

            return self.build_response(resource=resource, rows=rows, request=request)

        return wrapped

    return action_decorator

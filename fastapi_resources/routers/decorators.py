import functools
from typing import Callable, Literal

methods = Literal["post", "get", "patch", "delete"]


def action(detail: bool, methods: list[methods] | None = None, **kwargs):
    methods = methods or ["get"]

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
            next = None
            count = None

            if not detail:
                rows, next, count = rows

            return self.build_response(
                resource=resource, rows=rows, request=request, next=next, count=count
            )

        return wrapped

    return action_decorator

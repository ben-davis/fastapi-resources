import inspect
import logging
from collections import defaultdict
from typing import Any, Callable

from fastapi_resources.domain import Command, Event

logger = logging.getLogger(__name__)


class MessageBus:
    def __init__(self):
        self._command_handlers: dict[type, Callable[..., Any]] = {}
        self._event_handlers: dict[type, list[Callable[..., Any]]] = defaultdict(list)

    def register(self, message_type: type, handler: Callable[..., Any]) -> None:
        if issubclass(message_type, Command):
            self._command_handlers[message_type] = handler
        elif issubclass(message_type, Event):
            self._event_handlers[message_type].append(handler)
        else:
            raise ValueError(f"{message_type} is not a Command or Event subclass")

    def register_resource(self, commands, handlers) -> None:
        """Register all CRUD command handlers from a build_handlers namespace."""
        for cmd_attr, handler_attr in (
            ("Create", "create"),
            ("Update", "update"),
            ("Delete", "delete"),
        ):
            cmd_type = getattr(commands, cmd_attr, None)
            handler = getattr(handlers, handler_attr, None)
            if cmd_type is not None and handler is not None:
                self.register(cmd_type, handler)

    def handle(self, message):
        """Dispatch a command or event, draining any domain events afterward."""
        queue = [message]
        result = None

        while queue:
            msg = queue.pop(0)
            if isinstance(msg, Command):
                result = self._handle_command(msg, queue)
            elif isinstance(msg, Event):
                self._handle_event(msg, queue)

        return result

    def _handle_command(self, cmd: Command, queue: list):
        handler = self._command_handlers.get(type(cmd))
        if handler is None:
            raise ValueError(f"No handler registered for command {type(cmd).__name__}")

        result = handler(cmd)
        queue.extend(self._collect_events(handler))
        return result

    def _handle_event(self, event: Event, queue: list):
        for handler in self._event_handlers.get(type(event), []):
            try:
                handler(event)
                queue.extend(self._collect_events(handler))
            except Exception:
                logger.exception(
                    "Event handler %s failed for %s", handler, type(event).__name__
                )

    def _collect_events(self, handler: Callable[..., Any]) -> list[Event]:
        """Drain domain events from the handler's default UoW parameter, if any."""
        sig = inspect.signature(handler)
        for param in sig.parameters.values():
            if param.default is inspect.Parameter.empty:
                continue
            uow = param.default
            if hasattr(uow, "collect_new_events"):
                return list(uow.collect_new_events())
        return []

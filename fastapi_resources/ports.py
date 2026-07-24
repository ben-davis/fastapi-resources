"""Ports — the abstractions consumers depend on (dependency inversion).

`Repository` and `UnitOfWork` describe the minimal surface application handlers
rely on. The concrete implementations (``BaseSqlAlchemyRepo``,
``SqlAlchemyUnitOfWork``) satisfy them structurally; applications type their
handlers against these and may extend ``UnitOfWork`` with domain-specific
members (e.g. ``current_user`` / app-specific repos).
"""
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class Repository(Protocol):
    def add(self, obj: Any) -> None: ...
    def get(self, id: Any, method: str = "retrieve", options: Optional[list] = None) -> Any: ...


@runtime_checkable
class UnitOfWork(Protocol):
    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, *args: Any) -> None: ...
    def repo_for(self, db_class: type) -> Repository: ...
    def commit(self) -> None: ...

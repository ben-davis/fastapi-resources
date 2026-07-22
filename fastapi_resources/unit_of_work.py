from abc import ABC, abstractmethod
from typing import Iterator

from fastapi_resources.domain import Event


class AbstractUnitOfWork(ABC):
    def __enter__(self) -> "AbstractUnitOfWork":
        return self

    def __exit__(self, *args):
        self.rollback()

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...

    @abstractmethod
    def collect_new_events(self) -> Iterator[Event]: ...

    def repo_for(self, db_class):
        """Find the repository on this UoW whose Db class matches db_class."""
        for attr_name in vars(self):
            repo = getattr(self, attr_name)
            if hasattr(repo, "Db") and repo.Db is db_class:
                return repo
        raise ValueError(
            f"No repository found on {type(self).__name__} for {db_class.__name__}. "
            f"Ensure your UoW assigns a repo with Db={db_class.__name__} in __enter__."
        )


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.collected_events: list[Event] = []

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self.session_factory()
        self.collected_events = []
        return self

    def __exit__(self, *args):
        super().__exit__(*args)
        self.session.close()

    def commit(self) -> None:
        # Flush first so freshly-added (pending) objects enter the identity_map;
        # otherwise their domain_events would be missed (they live in session.new).
        self.session.flush()
        # Collect domain events before committing (identity_map cleared after commit)
        for obj in list(self.session.identity_map.values()):
            events = list(getattr(obj, "domain_events", []))
            self.collected_events.extend(events)
            if hasattr(obj, "domain_events"):
                obj.domain_events.clear()
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def collect_new_events(self) -> Iterator[Event]:
        events = list(self.collected_events)
        self.collected_events.clear()
        yield from events

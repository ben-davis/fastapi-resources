"""Tests for build_handlers with a FakeUnitOfWork."""
from typing import Iterator

import pytest

from fastapi_resources.domain import Event
from fastapi_resources.handlers import build_handlers
from fastapi_resources.unit_of_work import AbstractUnitOfWork
from tests.resources.sqlalchemy_models import (
    Galaxy,
    GalaxyCommands,
    GalaxyRepo,
    Star,
    StarCommands,
    StarFilteredRepo,
    engine,
)
from tests.resources.sqlalchemy_base import Base
from sqlalchemy.orm import Session


@pytest.fixture(scope="module", autouse=True)
def _db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session():
    with Session(engine) as s:
        yield s
        s.rollback()


class FakeUoW(AbstractUnitOfWork):
    """UoW backed by a real SQLAlchemy session but flushes instead of committing."""

    def __init__(self, session: Session):
        self._session = session
        self.collected_events: list[Event] = []

    def __enter__(self) -> "FakeUoW":
        self.stars = StarFilteredRepo(self._session)
        self.galaxies = GalaxyRepo(self._session)
        self.collected_events = []
        return self

    def commit(self) -> None:
        for obj in list(self._session.identity_map.values()):
            events = list(getattr(obj, "domain_events", []))
            self.collected_events.extend(events)
            if hasattr(obj, "domain_events"):
                obj.domain_events.clear()
        self._session.flush()

    def rollback(self) -> None:
        self._session.rollback()

    def collect_new_events(self) -> Iterator[Event]:
        events = list(self.collected_events)
        self.collected_events.clear()
        yield from events

    def __exit__(self, exc_type, *args):
        if exc_type is not None:
            self.rollback()


class TestDefaultHandlers:
    def test_create_returns_pk(self, session: Session):
        uow = FakeUoW(session)
        handlers = build_handlers(Galaxy, GalaxyCommands, uow)

        pk = handlers.create(GalaxyCommands.Create(name="Milky Way"))

        assert pk is not None
        assert isinstance(pk, int)

    def test_create_persists_to_db(self, session: Session):
        uow = FakeUoW(session)
        handlers = build_handlers(Galaxy, GalaxyCommands, uow)

        pk = handlers.create(GalaxyCommands.Create(name="Andromeda"))

        galaxy = session.get(Galaxy, pk)
        assert galaxy is not None
        assert galaxy.name == "Andromeda"

    def test_create_emits_created_event(self, session: Session):
        uow = FakeUoW(session)
        handlers = build_handlers(Galaxy, GalaxyCommands, uow)

        handlers.create(GalaxyCommands.Create(name="Triangulum"))

        events = list(uow.collected_events)
        assert len(events) == 1
        assert isinstance(events[0], GalaxyCommands.Created)

    def test_update_changes_field(self, session: Session):
        galaxy = Galaxy(name="Old Name")
        session.add(galaxy)
        session.flush()

        uow = FakeUoW(session)
        handlers = build_handlers(Galaxy, GalaxyCommands, uow)

        handlers.update(GalaxyCommands.Update(id=galaxy.id, name="New Name"))

        session.expire(galaxy)
        galaxy = session.get(Galaxy, galaxy.id)
        assert galaxy.name == "New Name"

    def test_update_emits_updated_event(self, session: Session):
        galaxy = Galaxy(name="Temp")
        session.add(galaxy)
        session.flush()

        uow = FakeUoW(session)
        handlers = build_handlers(Galaxy, GalaxyCommands, uow)

        handlers.update(GalaxyCommands.Update(id=galaxy.id, name="Updated"))

        events = list(uow.collected_events)
        assert any(isinstance(e, GalaxyCommands.Updated) for e in events)

    def test_delete_removes_from_db(self, session: Session):
        galaxy = Galaxy(name="To Delete")
        session.add(galaxy)
        session.flush()
        pk = galaxy.id

        uow = FakeUoW(session)
        handlers = build_handlers(Galaxy, GalaxyCommands, uow)

        handlers.delete(GalaxyCommands.Delete(id=pk))
        session.flush()

        assert session.get(Galaxy, pk) is None

    def test_delete_emits_deleted_event(self, session: Session):
        galaxy = Galaxy(name="To Delete 2")
        session.add(galaxy)
        session.flush()

        uow = FakeUoW(session)
        handlers = build_handlers(Galaxy, GalaxyCommands, uow)

        handlers.delete(GalaxyCommands.Delete(id=galaxy.id))

        events = list(uow.collected_events)
        assert any(isinstance(e, GalaxyCommands.Deleted) for e in events)


class TestHandlerWithPostInitFK:
    """Tests that init=False FK columns are set via setattr after construction."""

    def test_create_star_with_galaxy_id(self, session: Session):
        galaxy = Galaxy(name="Host Galaxy")
        session.add(galaxy)
        session.flush()

        uow = FakeUoW(session)
        handlers = build_handlers(Star, StarCommands, uow)

        pk = handlers.create(
            StarCommands.Create(name="Orbiting Star", galaxy_id=galaxy.id)
        )

        star = session.get(Star, pk)
        assert star.galaxy_id == galaxy.id

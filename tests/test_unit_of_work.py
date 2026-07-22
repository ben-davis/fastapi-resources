"""Tests for SqlAlchemyUnitOfWork event collection."""
import dataclasses

import pytest
from sqlalchemy.orm import Session, sessionmaker

from fastapi_resources.domain import Event
from fastapi_resources.unit_of_work import SqlAlchemyUnitOfWork
from tests.resources.sqlalchemy_base import Base
from tests.resources.sqlalchemy_models import Galaxy, engine


@pytest.fixture(scope="module", autouse=True)
def _db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@dataclasses.dataclass(frozen=True)
class GalaxyDiscovered(Event):
    name: str


def test_commit_collects_events_from_pending_object():
    """A freshly-added, un-flushed object's domain_events must still be collected.

    Regression guard: pending objects live in session.new, not identity_map, so
    commit() must flush before scanning identity_map or the events are lost.
    """
    session_factory = sessionmaker(engine)
    uow = SqlAlchemyUnitOfWork(session_factory)

    with uow:
        galaxy = Galaxy(name="Whirlpool")
        uow.session.add(galaxy)  # no flush — object is pending, in session.new
        galaxy.domain_events = [GalaxyDiscovered(name="Whirlpool")]
        uow.commit()

    events = list(uow.collect_new_events())
    assert len(events) == 1
    assert isinstance(events[0], GalaxyDiscovered)
    assert events[0].name == "Whirlpool"

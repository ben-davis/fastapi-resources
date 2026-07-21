from typing import Iterator, NamedTuple

import pytest
from sqlalchemy.orm import Session, close_all_sessions

from fastapi_resources import MessageBus, build_handlers
from fastapi_resources.domain import Event
from fastapi_resources.unit_of_work import AbstractUnitOfWork
from tests.resources.sqlalchemy_models import (
    Base,
    Element,
    Galaxy,
    GalaxyCommands,
    GalaxyRepo,
    Moon,
    MoonCommands,
    MoonRepo,
    Planet,
    PlanetCommands,
    PlanetRepo,
    Star,
    StarCommands,
    StarFilteredRepo,
    engine,
)


class OneTimeData(NamedTuple):
    sun: Star
    earth: Planet
    element: Element
    sun_id: int
    earth_id: str
    element_id: int


def make_test_bus(session: Session) -> MessageBus:
    """Build a MessageBus backed by handlers that share the given session.

    The handlers flush (not commit) so the outer test transaction controls rollback.
    """

    class _TestUoW(AbstractUnitOfWork):
        def __enter__(self) -> "_TestUoW":
            self.stars = StarFilteredRepo(session)
            self.galaxies = GalaxyRepo(session)
            self.planets = PlanetRepo(session)
            self.moons = MoonRepo(session)
            self.collected_events: list[Event] = []
            return self

        def commit(self) -> None:
            for obj in list(session.identity_map.values()):
                events = list(getattr(obj, "domain_events", []))
                self.collected_events.extend(events)
                if hasattr(obj, "domain_events"):
                    obj.domain_events.clear()
            session.flush()

        def rollback(self) -> None:
            pass  # outer transaction handles cleanup

        def collect_new_events(self) -> Iterator[Event]:
            events = list(self.collected_events)
            self.collected_events.clear()
            yield from events

        def __exit__(self, exc_type, *args):
            if exc_type is not None:
                self.rollback()

    uow = _TestUoW()

    star_handlers = build_handlers(Star, StarCommands, uow)
    galaxy_handlers = build_handlers(Galaxy, GalaxyCommands, uow)
    planet_handlers = build_handlers(Planet, PlanetCommands, uow)
    moon_handlers = build_handlers(Moon, MoonCommands, uow)

    bus = MessageBus()
    bus.register_resource(StarCommands, star_handlers)
    bus.register_resource(GalaxyCommands, galaxy_handlers)
    bus.register_resource(PlanetCommands, planet_handlers)
    bus.register_resource(MoonCommands, moon_handlers)

    return bus


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(engine)

    one_time_data: OneTimeData

    with Session(engine) as session:
        star = Star(name="Sun")
        planet = Planet(name="Earth", star=star)
        element = Element(name="helium")
        session.add_all([star, planet, element])
        session.commit()

        assert star.id
        assert planet.id

        one_time_data = OneTimeData(
            sun=star,
            earth=planet,
            sun_id=star.id,
            earth_id=planet.id,
            element=element,
            element_id=element.id,
        )

    yield one_time_data

    close_all_sessions()

    Base.metadata.drop_all(engine)

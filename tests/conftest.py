from typing import NamedTuple

import pytest
from sqlalchemy.orm import close_all_sessions
from sqlmodel import Session
from tests.resources.sqlmodel_models import Planet, Star, engine, registry


class OneTimeData(NamedTuple):
    sun_id: int
    earth_id: str


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    registry.metadata.create_all(engine)

    one_time_data: OneTimeData

    # Test data used in list endpoint tests
    with Session(engine) as session:
        star = Star(name="Sun")
        planet = Planet(name="Earth", star=star)
        session.add(star)
        session.add(planet)
        session.commit()

        assert star.id
        assert planet.id

        one_time_data = OneTimeData(sun_id=star.id, earth_id=str(planet.id))

    yield one_time_data

    close_all_sessions()

    registry.metadata.drop_all(engine)

from typing import NamedTuple

import pytest
from sqlalchemy.orm import Session, close_all_sessions

from tests.resources.sqlalchemy_models import Base, Planet, Star, engine


class OneTimeData(NamedTuple):
    sun: Star
    earth: Planet
    sun_id: int
    earth_id: str


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(engine)

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

        one_time_data = OneTimeData(
            sun=star, earth=planet, sun_id=star.id, earth_id=planet.id
        )

    yield one_time_data

    close_all_sessions()

    Base.metadata.drop_all(engine)

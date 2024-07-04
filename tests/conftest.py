from typing import NamedTuple

import pytest
from sqlalchemy.orm import Session, close_all_sessions

from tests.resources.sqlalchemy_models import Base, Element, Planet, Star, engine


class OneTimeData(NamedTuple):
    sun: Star
    earth: Planet
    element: Element
    sun_id: int
    earth_id: str
    element_id: int


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(engine)

    one_time_data: OneTimeData

    # Test data used in list endpoint tests
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

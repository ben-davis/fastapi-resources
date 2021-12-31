import pprint
from typing import Optional

import pytest
from fastapi import Request
from sqlalchemy.orm.session import close_all_sessions
from sqlmodel import Session

from fastapi_rest_framework.resources.sqlmodel import (
    Relationships,
    SQLModelRelationshipInfo,
    SQLResourceProtocol,
)
from tests.resources.sqlmodel_models import (
    Galaxy,
    GalaxyResource,
    Planet,
    PlanetResource,
    Star,
    StarCreate,
    StarResource,
    engine,
    registry,
)
from tests.utils import assert_num_queries


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    registry.metadata.create_all(engine)

    yield

    close_all_sessions()

    registry.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def session():
    conn = engine.connect()
    transaction = conn.begin()
    session = Session(bind=conn)

    yield session

    session.close()
    transaction.rollback()
    conn.close()


class TestRelationships:
    def test_inclusion_validation_success(self, session: Session):
        # Validation happens on instantiation
        GalaxyResource(
            session=session,
            inclusions=[
                ["stars", "planets", "favorite_galaxy", "stars"],
                ["favorite_planets", "star"],
            ],
        )

    def test_inclusion_validation_invalid(self, session: Session):
        with pytest.raises(AssertionError):
            GalaxyResource(
                session=session,
                inclusions=[
                    ["stars", "yolo", "favorite_galaxy", "stars"],
                ],
            )

    def test_is_recursive_graph(self, session: Session):
        resource = GalaxyResource(session=session)
        relationships = resource.get_relationships()

        # Galaxy -> Stars
        galaxy_to_stars = relationships["stars"]
        assert galaxy_to_stars.schema_with_relationships.schema == Star
        assert galaxy_to_stars.schema_with_relationships.relationships
        assert galaxy_to_stars.many

        # Galaxy -> Favorite Planets
        galaxy_to_favorite_planets = relationships["favorite_planets"]
        assert galaxy_to_favorite_planets.schema_with_relationships.schema == Planet
        assert galaxy_to_favorite_planets.schema_with_relationships.relationships
        assert galaxy_to_favorite_planets.many

        # Galaxy -> Favorite Planets -> Star
        favorite_planets_to_star = (
            galaxy_to_favorite_planets.schema_with_relationships.relationships["star"]
        )
        assert favorite_planets_to_star.schema_with_relationships.schema == Star
        assert not favorite_planets_to_star.many

        # Check it's not reused as the parent is different
        assert not (
            favorite_planets_to_star.schema_with_relationships
            is galaxy_to_stars.schema_with_relationships
        )

        # Galaxy -> Stars -> Planets
        stars_to_planets = galaxy_to_stars.schema_with_relationships.relationships[
            "planets"
        ]
        assert stars_to_planets.schema_with_relationships.schema == Planet
        assert stars_to_planets.many

        # Galaxy -> Stars -> Planets -> Favorite Galaxy
        planet_to_favorite_galaxy = (
            stars_to_planets.schema_with_relationships.relationships["favorite_galaxy"]
        )
        assert planet_to_favorite_galaxy.schema_with_relationships.schema == Galaxy
        assert not planet_to_favorite_galaxy.many

        # Galaxy -> Stars -> Planets -> Favorite Galaxy -> Star
        favorite_galaxy_to_stars = (
            planet_to_favorite_galaxy.schema_with_relationships.relationships["stars"]
        )
        assert favorite_galaxy_to_stars.schema_with_relationships.schema == Star
        assert not planet_to_favorite_galaxy.many

        # Check the Planet relationship is not reused as the parent is different
        assert not (
            galaxy_to_favorite_planets.schema_with_relationships
            is stars_to_planets.schema_with_relationships
        )

        # Check that true cycles are not repeated, which in this test is
        # Galaxy -> Stars -> Planet -> Favorite Galaxy -> Stars.
        # We want to check that the Star relationship at the leaf is reused
        # as it shares a parent.
        assert (
            galaxy_to_stars.schema_with_relationships
            is favorite_galaxy_to_stars.schema_with_relationships
        )


class TestRetrieve:
    def test_retrieve(self, session: Session):
        star = Star(name="Sirius")
        session.add(star)
        session.commit()
        session.refresh(star)

        assert star.id

        resource = StarResource(session=session)
        star_retrieve = resource.retrieve(id=star.id)

        assert star_retrieve.name == "Sirius"

    def test_include(self, session: Session):
        star = Star(name="Sun")
        session.add(star)
        session.commit()
        session.refresh(star)

        planet = Planet(name="Earth", star_id=star.id)
        session.add(planet)
        session.commit()
        session.refresh(planet)

        assert star.id
        assert planet.id

        # We need to save this otherwise planet.id will cause a new query to be emitted.
        planet_id = planet.id

        resource = PlanetResource(session=session, inclusions=[["star"]])

        # Expire so we know we're starting from fresh
        session.expire_all()

        with assert_num_queries(engine=engine, num=1):
            planet_retrieve = resource.retrieve(id=planet_id)
            related = resource.get_related(planet_retrieve, "star")

        assert related.name == "Sun"


# star = resource.create(model=StarCreate(name="Series"))

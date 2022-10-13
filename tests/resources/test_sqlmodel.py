import pytest
from sqlalchemy.orm import exc as sa_exceptions
from sqlmodel import Session, select

from fastapi_resources.resources.sqlmodel.exceptions import NotFound
from fastapi_resources.resources.sqlmodel.resources import SQLModelResource
from tests.conftest import OneTimeData
from tests.resources.sqlmodel_models import (
    Galaxy,
    GalaxyResource,
    Planet,
    PlanetResource,
    Star,
    StarCreate,
    StarResource,
    StarUpdate,
    engine,
)
from tests.utils import assert_num_queries


@pytest.fixture(scope="module")
def session():
    conn = engine.connect()
    transaction = conn.begin()
    session = Session(bind=conn)

    yield session

    session.close()
    transaction.rollback()
    conn.close()


class TestContext:
    def test_saves_context(self):
        resource = GalaxyResource(context={"request": 123})
        assert resource.context["request"] == 123


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

    def test_get_related(self, session: Session):
        resource = GalaxyResource(
            session=session,
            inclusions=[],
        )

        galaxy = Galaxy(name="Milky Way")
        session.add(galaxy)
        session.commit()

        star = Star(name="Sun", galaxy_id=galaxy.id)
        session.add(star)
        session.commit()

        andromeda = Galaxy(name="Andromeda")
        session.add(andromeda)
        session.commit()

        andromedae = Star(name="Andromedae", galaxy_id=galaxy.id)
        session.add(andromedae)
        session.commit()

        planet = Planet(name="Earth", star_id=star.id, favorite_galaxy_id=andromeda.id)
        session.add(planet)
        session.commit()

        related_objects = resource.get_related(
            obj=galaxy,
            inclusion=["stars", "planets", "favorite_galaxy", "stars"],
        )

        assert related_objects[0].obj == star
        assert related_objects[0].resource == StarResource
        assert related_objects[1].obj == andromedae
        assert related_objects[1].resource == StarResource
        assert related_objects[2].obj == planet
        assert related_objects[2].resource == PlanetResource
        assert related_objects[3].obj == andromeda
        assert related_objects[3].resource == GalaxyResource

    def test_get_related_works_for_empty_relationships(self, session: Session):
        vega = Star(name="Vega")

        star_resource = StarResource(
            session=session,
            inclusions=[],
        )

        session.add(vega)
        session.commit()

        related_objects = star_resource.get_related(
            obj=vega,
            inclusion=["planets"],
        )
        assert related_objects == []

        related_objects = star_resource.get_related(
            obj=vega,
            inclusion=["galaxy"],
        )
        assert related_objects == []


class TestWhere:
    def test_used_in_get_object(self, session: Session):
        original_resource = SQLModelResource.registry[Star]

        class FilteredStarResource(SQLModelResource[Star]):
            engine = engine
            name = "star"
            Db = Star

            def get_where(self):
                return [Star.name == "Gazorbo"]

        star = Star(name="Sirius")
        session.add(star)
        session.commit()
        session.refresh(star)

        assert star.id

        resource = FilteredStarResource(session=session)
        with pytest.raises(NotFound):
            resource.retrieve(id=star.id)

        # Reset the registry
        SQLModelResource.registry[Star] = original_resource

    def test_used_in_update(self, session: Session, setup_database: OneTimeData):
        original_resource = SQLModelResource.registry[Planet]

        resource = StarResource(session=session, context={"request": 123})

        # Replace the planet relationship with one that filters
        class FilteredPlanetResource(SQLModelResource):
            engine = engine
            name = "planet"
            Db = Planet

            def get_where(self):
                assert self.context["request"] == 123
                return [Planet.name == "Hoth"]

        SQLModelResource.registry[Planet] = FilteredPlanetResource

        with pytest.raises(NotFound):
            resource.update(
                id=setup_database.sun_id,
                attributes=StarUpdate(name="Milky Way").dict(exclude_unset=True),
                relationships={
                    "planets": [
                        setup_database.earth_id,
                    ],
                },
            )

        SQLModelResource.registry[Planet] = original_resource

    def test_used_in_create(self, session: Session, setup_database: OneTimeData):
        original_resource = SQLModelResource.registry[Planet]

        resource = StarResource(session=session, context={"request": 123})

        # Replace the planet relationship with one that filters
        class FilteredPlanetResource(SQLModelResource):
            engine = engine
            name = "planet"
            Db = Planet

            def get_where(self):
                assert self.context["request"] == 123
                return [Planet.name == "Hoth"]

        SQLModelResource.registry[Planet] = FilteredPlanetResource

        with pytest.raises(NotFound):
            resource.create(
                attributes=StarCreate(name="Milky Way").dict(exclude_unset=True),
                relationships={"planets": [setup_database.earth_id]},
                name="Passed Manually",
            )

        SQLModelResource.registry[Planet] = original_resource


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

    def test_include_preselects(self, session: Session):
        galaxy = Galaxy(name="Milky Way")
        session.add(galaxy)
        session.commit()
        session.refresh(galaxy)

        star = Star(name="Sun", galaxy_id=galaxy.id)
        session.add(star)
        session.commit()
        session.refresh(star)

        planet = Planet(name="Earth", star_id=star.id)
        session.add(planet)
        session.commit()
        session.refresh(planet)

        assert star.id
        assert planet.id
        assert galaxy.id

        # We need to save this otherwise planet.id will cause a new query to be emitted.
        galaxy_id = galaxy.id

        resource = GalaxyResource(session=session, inclusions=[["stars", "planets"]])

        # Expire so we know we're starting from fresh
        session.expire_all()

        with assert_num_queries(engine=engine, num=1):
            galaxy_retrieve = resource.retrieve(id=galaxy_id)
            related = resource.get_related(galaxy_retrieve, ["stars", "planets"])

        assert related[0].obj.name == "Sun"


class TestList:
    def test_list(self, session: Session):
        resource = StarResource(session=session)
        star_list = resource.list()

        # Some number of stars will have been created during the session, so as
        # long as some exist, then we're good.
        assert star_list
        assert star_list[0].__tablename__ == "star"


class TestCreate:
    def test_create(self, session: Session):
        resource = StarResource(session=session)
        star_create = resource.create(
            attributes=StarCreate(name="Sirius").dict(exclude_unset=True)
        )

        star_db = session.exec(select(Star).where(Star.id == star_create.id)).one()

        assert star_create.name == "Sirius"
        assert star_db.name == "Sirius"

    def test_extra_attributes(self, session: Session):
        resource = StarResource(session=session)
        star_create = resource.create(
            attributes=StarCreate(name="Milky Way").dict(exclude_unset=True),
            name="Passed Manually",
        )

        assert star_create.name == "Passed Manually"

    def test_relationships(self, session: Session, setup_database: OneTimeData):
        resource = StarResource(session=session)

        star_create = resource.create(
            attributes=StarCreate(name="Milky Way").dict(exclude_unset=True),
            relationships={"planets": [setup_database.earth_id]},
            name="Passed Manually",
        )

        assert star_create.name == "Passed Manually"
        assert len(star_create.planets) == 1
        assert str(star_create.planets[0].id) == setup_database.earth_id


class TestUpdate:
    def test_update(self, session: Session):
        star = Star(name="Sirius")
        session.add(star)
        session.commit()
        session.refresh(star)

        assert star.id

        resource = StarResource(session=session)
        star_create = resource.update(
            id=star.id, attributes=StarUpdate(name="Milky Way").dict(exclude_unset=True)
        )

        star_db = session.exec(select(Star).where(Star.id == star.id)).one()

        assert star_create.name == "Milky Way"
        assert star_db.name == "Milky Way"

    def test_extra_attributes(self, session: Session):
        star = Star(name="Sirius")
        session.add(star)
        session.commit()
        session.refresh(star)

        assert star.id

        resource = StarResource(session=session)
        star_create = resource.update(
            id=star.id,
            attributes=StarUpdate().dict(exclude_unset=True),
            name="Passed Manually",
        )

        assert star_create.name == "Passed Manually"

    def test_update_relationships(self, session: Session):
        star = Star(name="Sirius")
        milky_way = Galaxy(name="Milky Way")
        earth = Planet(name="Earth")
        mars = Planet(name="Mars")
        mercury = Planet(name="Mercury")

        # No default galaxy, but give it a planet
        star.planets.append(mercury)

        session.add(star)
        session.add(milky_way)
        session.add(earth)
        session.add(mars)
        session.add(mercury)

        session.commit()
        session.refresh(star)

        assert star.id
        assert earth.id
        assert mars.id
        assert milky_way.id
        assert len(star.planets) == 1

        resource = StarResource(session=session)

        star_update = resource.update(
            id=star.id,
            attributes=StarUpdate(name="Milky Way").dict(exclude_unset=True),
            relationships={
                "planets": [
                    earth.id,
                    mars.id,
                ],
                "galaxy": milky_way.id,
            },
        )

        star_db = session.exec(select(Star).where(Star.id == star.id)).one()

        for s in (star_update, star_db):
            assert s.name == "Milky Way"
            assert s.galaxy == milky_way
            assert set(p.id for p in s.planets) == set((earth.id, mars.id))


class TestDelete:
    def test_delete(self, session: Session):
        star = Star(name="Sirius")
        session.add(star)
        session.commit()
        session.refresh(star)

        assert star.id

        resource = StarResource(session=session)
        resource.delete(id=star.id)

        with pytest.raises(sa_exceptions.NoResultFound):
            session.exec(select(Star).where(Star.id == star.id)).one()

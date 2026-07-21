import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import exc as sa_exceptions

from fastapi_resources import build_sqlalchemy_repo
from fastapi_resources.resources.sqlalchemy.base import BaseSQLAlchemyResource
from fastapi_resources.resources.sqlalchemy.exceptions import NotFound
from tests.conftest import OneTimeData, make_test_bus
from tests.resources.sqlalchemy_models import (
    Element,
    ElementResource,
    Galaxy,
    GalaxyResource,
    MoonResource,
    Planet,
    PlanetResource,
    Star,
    StarCommands,
    StarCreate,
    StarElementAssociation,
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


@pytest.fixture(scope="module")
def messagebus_handle(session):
    bus = make_test_bus(session)
    return bus.handle


class TestContext:
    def test_saves_context(self):
        resource = GalaxyResource(context={"request": 123})
        assert resource.context["request"] == 123


class TestRelationships:
    def test_inclusion_validation_success(self, session: Session, messagebus_handle):
        GalaxyResource(
            session=session,
            messagebus_handle=messagebus_handle,
            inclusions=[
                ["stars", "planets", "favorite_galaxy", "stars"],
                ["favorite_planets", "star"],
            ],
        )

    def test_inclusion_validation_invalid(self, session: Session, messagebus_handle):
        with pytest.raises(AssertionError):
            GalaxyResource(
                session=session,
                messagebus_handle=messagebus_handle,
                inclusions=[
                    ["stars", "yolo", "favorite_galaxy", "stars"],
                ],
            )

    def test_is_recursive_graph(self, session: Session, messagebus_handle):
        resource = GalaxyResource(session=session, messagebus_handle=messagebus_handle)
        relationships = resource.relationships

        galaxy_to_stars = relationships["stars"]
        assert galaxy_to_stars.schema_with_relationships.schema == Star
        assert galaxy_to_stars.schema_with_relationships.relationships
        assert galaxy_to_stars.many

        galaxy_to_favorite_planets = relationships["favorite_planets"]
        assert galaxy_to_favorite_planets.schema_with_relationships.schema == Planet
        assert galaxy_to_favorite_planets.schema_with_relationships.relationships
        assert galaxy_to_favorite_planets.many

        favorite_planets_to_star = (
            galaxy_to_favorite_planets.schema_with_relationships.relationships["star"]
        )
        assert favorite_planets_to_star.schema_with_relationships.schema == Star
        assert not favorite_planets_to_star.many

        assert not (
            favorite_planets_to_star.schema_with_relationships
            is galaxy_to_stars.schema_with_relationships
        )

        stars_to_elements = galaxy_to_stars.schema_with_relationships.relationships[
            "elements"
        ]
        assert stars_to_elements.schema_with_relationships.schema == Element
        assert stars_to_elements.many

        stars_to_planets = galaxy_to_stars.schema_with_relationships.relationships[
            "planets"
        ]
        assert stars_to_planets.schema_with_relationships.schema == Planet
        assert stars_to_planets.many

        planet_to_favorite_galaxy = (
            stars_to_planets.schema_with_relationships.relationships["favorite_galaxy"]
        )
        assert planet_to_favorite_galaxy.schema_with_relationships.schema == Galaxy
        assert not planet_to_favorite_galaxy.many

        favorite_galaxy_to_stars = (
            planet_to_favorite_galaxy.schema_with_relationships.relationships["stars"]
        )
        assert favorite_galaxy_to_stars.schema_with_relationships.schema == Star
        assert not planet_to_favorite_galaxy.many

        assert not (
            galaxy_to_favorite_planets.schema_with_relationships
            is stars_to_planets.schema_with_relationships
        )

        assert (
            galaxy_to_stars.schema_with_relationships
            is favorite_galaxy_to_stars.schema_with_relationships
        )

    def test_get_related(self, session: Session, messagebus_handle):
        resource = GalaxyResource(
            session=session,
            messagebus_handle=messagebus_handle,
            inclusions=[],
        )

        galaxy = Galaxy(name="Milky Way")
        session.add(galaxy)
        session.flush()

        star = Star(name="Sun", galaxy=galaxy)
        session.add(star)
        session.flush()

        hydrogen = Element(name="hydrogen")
        hydrogen_association = StarElementAssociation(element=hydrogen, star=star)
        session.add_all([hydrogen, hydrogen_association])
        session.flush()

        andromeda = Galaxy(name="Andromeda")
        session.add(andromeda)
        session.flush()

        andromedae = Star(name="Andromedae", galaxy=andromeda)
        session.add(andromedae)
        session.flush()

        planet = Planet(name="Earth", star=star, favorite_galaxy=galaxy)
        session.add(planet)
        session.flush()

        planet_resource = PlanetResource(
            session=session,
            messagebus_handle=messagebus_handle,
            inclusions=[],
        )
        related_objects = planet_resource.get_related(
            obj=planet,
            inclusion=[
                "favorite_galaxy",
                "stars",
                "elements",
            ],
        )
        assert related_objects[0].obj == galaxy
        assert related_objects[1].obj == star
        assert related_objects[2].obj == hydrogen

        # Back-populates already added planet to galaxy.favorite_planets via the
        # Planet constructor. Expire to load fresh from DB so we get a single entry.
        session.expire(galaxy)

        related_objects = resource.get_related(
            obj=galaxy,
            inclusion=[
                "stars",
                "planets",
                "favorite_galaxy",
                "stars",
            ],
        )

        assert related_objects[0].obj == star
        assert related_objects[0].resource == StarResource
        assert related_objects[1].obj == planet
        assert related_objects[1].resource == PlanetResource
        assert related_objects[2].obj == galaxy
        assert related_objects[2].resource == GalaxyResource

        related_objects = resource.get_related(
            obj=galaxy,
            inclusion=[
                "favorite_planets",
                "star",
                "elements",
            ],
        )

        assert related_objects[0].obj == planet
        assert related_objects[0].resource == PlanetResource
        assert related_objects[1].obj == star
        assert related_objects[1].resource == StarResource
        assert related_objects[2].obj == hydrogen
        assert related_objects[2].resource == ElementResource

    def test_get_related_works_for_empty_relationships(
        self, session: Session, messagebus_handle
    ):
        vega = Star(name="Vega")

        star_resource = StarResource(
            session=session,
            messagebus_handle=messagebus_handle,
            inclusions=[],
        )

        session.add(vega)
        session.flush()

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
    def test_used_in_get_object(self, session: Session, messagebus_handle):
        original_resource = BaseSQLAlchemyResource.registry[Star]

        _StarBaseRepo = build_sqlalchemy_repo(Star)

        class GazorboStarRepo(_StarBaseRepo):
            def get_where(self, method):
                return [Star.name == "Gazorbo"]

        class FilteredStarResource(StarResource):
            name = "star"
            Db = Star
            Repo = GazorboStarRepo
            commands = StarCommands

        star = Star(name="Sirius")
        session.add(star)
        session.flush()

        assert star.id

        resource = FilteredStarResource(session=session, messagebus_handle=messagebus_handle)
        with pytest.raises(NotFound):
            resource.retrieve(id=star.id)

        BaseSQLAlchemyResource.registry[Star] = original_resource


class TestRetrieve:
    def test_retrieve(self, session: Session, messagebus_handle):
        star = Star(name="Sirius")
        session.add(star)
        session.flush()

        assert star.id

        resource = StarResource(session=session, messagebus_handle=messagebus_handle)
        star_retrieve = resource.retrieve(id=star.id)

        assert star_retrieve.name == "Sirius"

    def test_include_preselects(self, session: Session, messagebus_handle):
        galaxy = Galaxy(name="Milky Way")
        session.add(galaxy)
        session.flush()

        star = Star(name="Sun", galaxy=galaxy)
        session.add(star)
        session.flush()

        planet = Planet(name="Earth", star=star)
        session.add(planet)
        session.flush()

        assert star.id
        assert planet.id
        assert galaxy.id

        galaxy_id = galaxy.id

        resource = GalaxyResource(
            session=session,
            messagebus_handle=messagebus_handle,
            inclusions=[["stars", "planets"]],
        )

        session.expire_all()

        with assert_num_queries(engine=engine, num=1):
            galaxy_retrieve = resource.retrieve(id=galaxy_id)
            related = resource.get_related(galaxy_retrieve, ["stars", "planets"])

        assert related[0].obj.name == "Sun"


class TestList:
    def test_list(self, session: Session, messagebus_handle):
        resource = StarResource(session=session, messagebus_handle=messagebus_handle)
        star_list, next, count = resource.list()

        assert star_list
        assert star_list[0].__tablename__ == "star"

        assert next is None
        assert count


class TestCreate:
    def test_create(self, session: Session, messagebus_handle):
        resource = StarResource(session=session, messagebus_handle=messagebus_handle)
        star_create = resource.create(
            attributes=StarCreate(name="Sirius").model_dump(exclude_unset=True)
        )

        assert star_create.name == "Sirius"
        assert star_create.id

        star_db = session.scalars(
            select(Star).where(Star.id == star_create.id)
        ).one()
        assert star_db.name == "Sirius"

    def test_extra_attributes(self, session: Session, messagebus_handle):
        resource = StarResource(session=session, messagebus_handle=messagebus_handle)
        star_create = resource.create(
            attributes=StarCreate(name="Milky Way").model_dump(exclude_unset=True),
            name="Passed Manually",
        )

        assert star_create.name == "Passed Manually"

    def test_required_relationships(
        self, session: Session, messagebus_handle, setup_database: OneTimeData
    ):
        resource = MoonResource(session=session, messagebus_handle=messagebus_handle)

        moon_create = resource.create(
            attributes={"name": "Big Moon"},
            relationships={"planet": setup_database.earth_id},
        )

        assert moon_create.name == "Big Moon"
        assert moon_create.planet_id == setup_database.earth_id
        assert moon_create.planet


class TestUpdate:
    def test_update(self, session: Session, messagebus_handle):
        star = Star(name="Sirius")
        session.add(star)
        session.flush()

        assert star.id

        resource = StarResource(session=session, messagebus_handle=messagebus_handle)
        star_update = resource.update(
            id=star.id,
            attributes=StarUpdate(name="Milky Way").model_dump(exclude_unset=True),
        )

        star_db = session.scalars(select(Star).where(Star.id == star.id)).one()

        assert star_update.name == "Milky Way"
        assert star_db.name == "Milky Way"

    def test_extra_attributes(self, session: Session, messagebus_handle):
        star = Star(name="Sirius")
        session.add(star)
        session.flush()

        assert star.id

        resource = StarResource(session=session, messagebus_handle=messagebus_handle)
        star_update = resource.update(
            id=star.id,
            attributes=StarUpdate(name="ignored").model_dump(exclude_unset=True),
            name="Passed Manually",
        )

        assert star_update.name == "Passed Manually"

    def test_update_galaxy_relationship(self, session: Session, messagebus_handle):
        star = Star(name="Sirius")
        milky_way = Galaxy(name="Milky Way")
        session.add_all([star, milky_way])
        session.flush()

        assert star.id
        assert milky_way.id

        resource = StarResource(session=session, messagebus_handle=messagebus_handle)

        star_update = resource.update(
            id=star.id,
            attributes=StarUpdate(name="Milky Way Star").model_dump(exclude_unset=True),
            relationships={"galaxy": milky_way.id},
        )

        star_db = session.scalars(select(Star).where(Star.id == star.id)).one()

        assert star_update.name == "Milky Way Star"
        assert star_update.galaxy_id == milky_way.id
        assert star_db.galaxy_id == milky_way.id


class TestDelete:
    def test_delete(self, session: Session, messagebus_handle):
        star = Star(name="Sirius")
        session.add(star)
        session.flush()

        assert star.id

        resource = StarResource(session=session, messagebus_handle=messagebus_handle)
        resource.delete(id=star.id)

        with pytest.raises(sa_exceptions.NoResultFound):
            session.scalars(select(Star).where(Star.id == star.id)).one()

    def test_delete_all(self, session: Session, messagebus_handle):
        star = Star(name="Sirius")
        session.add(star)
        session.flush()

        assert star.id

        resource = StarResource(session=session, messagebus_handle=messagebus_handle)
        resource.delete_all()

        with pytest.raises(sa_exceptions.NoResultFound):
            session.scalars(select(Star).where(Star.id == star.id)).one()

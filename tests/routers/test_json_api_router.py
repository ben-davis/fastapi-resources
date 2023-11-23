from unittest.mock import patch

import pytest
from dirty_equals import IsStr
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fastapi_resources import routers
from tests.conftest import OneTimeData
from tests.resources.sqlalchemy_models import (
    Asteroid,
    AsteroidResource,
    Galaxy,
    GalaxyResource,
    Planet,
    PlanetResource,
    Star,
    StarResource,
    engine,
)
from tests.utils import assert_num_queries

app = FastAPI()

planet_router = routers.JSONAPIResourceRouter(resource_class=PlanetResource)
star_router = routers.JSONAPIResourceRouter(resource_class=StarResource)
galaxy_router = routers.JSONAPIResourceRouter(resource_class=GalaxyResource)
asteroid_router = routers.JSONAPIResourceRouter(resource_class=AsteroidResource)

app.include_router(planet_router)
app.include_router(star_router)
app.include_router(galaxy_router)
app.include_router(asteroid_router)


client = TestClient(app)


@pytest.fixture(scope="function")
def session():
    conn = engine.connect()
    transaction = conn.begin()
    session = Session(bind=conn)

    original_get_resource_kwargs = routers.JSONAPIResourceRouter.get_resource_kwargs

    # Patch the SQLResource's session
    def get_resource_kwargs(self: routers.JSONAPIResourceRouter, request: Request):
        return {
            **original_get_resource_kwargs(self=self, request=request),
            "session": session,
        }

    with patch.object(
        routers.JSONAPIResourceRouter, "get_resource_kwargs", get_resource_kwargs
    ):
        yield session

    session.close()
    transaction.rollback()
    conn.close()


class TestRetrieve:
    def test_retrieve(self, session: Session, setup_database: OneTimeData):
        sun_id = setup_database.sun_id
        earth_id = setup_database.earth_id

        response = client.request("get", f"/stars/{sun_id}")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "id": str(sun_id),
                "type": "star",
                "attributes": {"name": "Sun", "brightness": 1, "color": ""},
                "relationships": {
                    "planets": {
                        "data": [
                            {
                                "type": "planet",
                                "id": str(earth_id),
                            }
                        ],
                    },
                    "galaxy": {
                        "data": None,
                    },
                },
            },
            "included": [],
            "links": {},
        }

    def test_retrieve_by_aliased_id(
        self, session: Session, setup_database: OneTimeData
    ):
        asteroid = Asteroid(name="big")
        session.add(asteroid)
        session.commit()

        response = client.get(f"/asteroids/big")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "id": "big",
                "type": "asteroid",
                "attributes": {},
                "relationships": {},
            },
            "included": [],
            "links": {},
        }

    def test_performance(self, session: Session, setup_database: OneTimeData):
        """
        Even though routers aren't aware of the internals of a resource, we want to make
        sure that the router is properly sending the preloads to the resource. The easiest
        and most reliable way to do that is via an integration test here.
        """
        # SELECT rows
        # SELECT count
        with assert_num_queries(engine=engine, num=2):
            response = client.get(f"/stars")
            assert response.status_code == 200

    def test_include(self, session: Session, setup_database: OneTimeData):
        sun_id = setup_database.sun_id
        earth_id = setup_database.earth_id

        response = client.get(f"/planets/{earth_id}?include=star")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "id": earth_id,
                "attributes": {
                    "name": "Earth",
                },
                "type": "planet",
                "relationships": {
                    "favorite_galaxy": {
                        "data": None,
                    },
                    "star": {
                        "data": {"type": "star", "id": "1"},
                    },
                },
            },
            "included": [
                {
                    "id": str(sun_id),
                    "type": "star",
                    "attributes": {"name": "Sun", "brightness": 1, "color": ""},
                    "relationships": {
                        "planets": {
                            "data": [
                                {
                                    "type": "planet",
                                    "id": str(earth_id),
                                }
                            ],
                        },
                        "galaxy": {
                            "data": None,
                        },
                    },
                }
            ],
            "links": {},
        }


class TestList:
    def test_list(self, session: Session, setup_database: OneTimeData):
        response = client.get(f"/stars")

        sun_id = setup_database.sun_id
        earth_id = setup_database.earth_id

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "id": str(sun_id),
                    "type": "star",
                    "attributes": {"name": "Sun", "brightness": 1, "color": ""},
                    "relationships": {
                        "planets": {
                            "data": [
                                {
                                    "type": "planet",
                                    "id": str(earth_id),
                                }
                            ],
                        },
                        "galaxy": {
                            "data": None,
                        },
                    },
                }
            ],
            "included": [],
            "links": {},
            "meta": {"count": 1},
        }

    def test_list_pagination(self, session: Session, setup_database: OneTimeData):
        priate = Star(name="Priate")
        session.add(priate)
        session.commit()

        priate_id = priate.id

        response = client.get(f"/stars?page[limit]=1")

        sun_id = setup_database.sun_id
        earth_id = setup_database.earth_id

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "id": str(sun_id),
                    "type": "star",
                    "attributes": {"name": "Sun", "brightness": 1, "color": ""},
                    "relationships": {
                        "planets": {
                            "data": [
                                {
                                    "type": "planet",
                                    "id": str(earth_id),
                                }
                            ],
                        },
                        "galaxy": {
                            "data": None,
                        },
                    },
                }
            ],
            "included": [],
            "links": {"next": "2"},
            "meta": {"count": 2},
        }

        # Get the next page
        response = client.get(f"/stars?page[limit]=1&page[cursor]=2")

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "id": str(priate_id),
                    "type": "star",
                    "attributes": {"name": "Priate", "brightness": 1, "color": ""},
                    "relationships": {
                        "planets": {
                            "data": [],
                        },
                        "galaxy": {
                            "data": None,
                        },
                    },
                }
            ],
            "included": [],
            "links": {},
            "meta": {"count": 2},
        }

    def test_list_pagination_with_filters(
        self, session: Session, setup_database: OneTimeData
    ):
        galaxy = Galaxy(name="StarWars")

        priate = Star(name="Priate", galaxy=galaxy)
        hoth = Star(name="Hoth", galaxy=galaxy)
        session.add_all([priate, hoth, galaxy])
        session.commit()
        session.refresh(galaxy)
        session.refresh(priate)
        session.refresh(hoth)

        priate_id = priate.id
        star_wars_id = galaxy.id

        response = client.get(f"/stars?page[limit]=1&filter[galaxy.name]={galaxy.name}")

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "id": str(priate_id),
                    "type": "star",
                    "attributes": {"name": "Priate", "brightness": 1, "color": ""},
                    "relationships": {
                        "planets": {
                            "data": [],
                        },
                        "galaxy": {
                            "data": {"type": "galaxy", "id": str(star_wars_id)},
                        },
                    },
                },
            ],
            "included": [],
            "links": {
                "next": "2",
            },
            "meta": {"count": 2},
        }

    def test_include(self, session: Session, setup_database: OneTimeData):
        sun_id = setup_database.sun_id
        earth_id = setup_database.earth_id

        # Add a planet with a new star and a galaxy, so we can test it still works even if
        # not all objects have the inclusion (so the OneTimeData star doesn't have a galaxy).
        star_wars_galaxy = Galaxy(name="Far Far Away")
        priate = Star(name="Priate", galaxy=star_wars_galaxy)
        mustafar = Planet(name="Mustafar", star=priate)

        # Add another planet with the OneTimeData star, so we can test inclusion are de-duped.
        mars = Planet(name="Mars", star=setup_database.sun)

        session.add(star_wars_galaxy)
        session.add(priate)
        session.add(mustafar)
        session.add(mars)
        session.commit()

        response = client.get(f"/planets?include=star.galaxy")

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "attributes": {
                        "name": "Earth",
                    },
                    "id": str(earth_id),
                    "type": "planet",
                    "relationships": {
                        "favorite_galaxy": {
                            "data": None,
                        },
                        "star": {
                            "data": {"id": str(sun_id), "type": "star"},
                        },
                    },
                },
                {
                    "attributes": {
                        "name": "Mustafar",
                    },
                    "id": str(mustafar.id),
                    "type": "planet",
                    "relationships": {
                        "favorite_galaxy": {
                            "data": None,
                        },
                        "star": {
                            "data": {"id": str(priate.id), "type": "star"},
                        },
                    },
                },
                {
                    "attributes": {
                        "name": "Mars",
                    },
                    "id": str(mars.id),
                    "type": "planet",
                    "relationships": {
                        "favorite_galaxy": {
                            "data": None,
                        },
                        "star": {
                            "data": {"id": str(sun_id), "type": "star"},
                        },
                    },
                },
            ],
            "included": [
                {
                    "attributes": {"name": "Sun", "brightness": 1, "color": ""},
                    "id": str(sun_id),
                    "type": "star",
                    "relationships": {
                        "galaxy": {
                            "data": None,
                        },
                        "planets": {
                            "data": [
                                {"type": "planet", "id": str(earth_id)},
                                {"type": "planet", "id": str(mars.id)},
                            ],
                        },
                    },
                },
                {
                    "attributes": {"name": "Priate", "brightness": 1, "color": ""},
                    "id": str(priate.id),
                    "type": "star",
                    "relationships": {
                        "galaxy": {
                            "data": {"type": "galaxy", "id": "1"},
                        },
                        "planets": {
                            "data": [{"type": "planet", "id": str(mustafar.id)}],
                        },
                    },
                },
                {
                    "attributes": {"name": "Far Far Away"},
                    "id": str(star_wars_galaxy.id),
                    "type": "galaxy",
                    "relationships": {
                        "stars": {
                            "data": [{"type": "star", "id": str(priate.id)}],
                        },
                        "favorite_planets": {
                            "data": [],
                        },
                    },
                },
            ],
            "links": {},
            "meta": {
                "count": 3,
            },
        }


class TestUpdate:
    def test_update(self, session: Session, setup_database: OneTimeData):
        sun_id = setup_database.sun_id
        sun = setup_database.sun

        galaxy = Galaxy(name="Milky Way")
        mercury = Planet(name="Mercury", star=sun)
        jupiter = Planet(name="Jupiter", star=sun)

        session.add(galaxy)
        session.add(mercury)
        session.add(jupiter)
        session.commit()

        response = client.patch(
            f"/stars/{sun_id}",
            json={
                "data": {
                    "type": "star",
                    "id": str(sun_id),
                    "attributes": {
                        "name": "Suntastic",
                        # This is a valid attribute, but is not included in Create, so
                        # should be ignored.
                        "color": "red",
                    },
                    "relationships": {
                        "galaxy": {"data": {"type": "galaxy", "id": str(galaxy.id)}},
                        "planets": {
                            "data": [
                                {"type": "planet", "id": str(jupiter.id)},
                            ]
                        },
                    },
                }
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "attributes": {"name": "Suntastic", "brightness": 1, "color": ""},
                "id": str(sun_id),
                "type": "star",
                "relationships": {
                    "galaxy": {
                        "data": {"type": "galaxy", "id": str(galaxy.id)},
                    },
                    "planets": {
                        "data": [
                            {"id": str(jupiter.id), "type": "planet"},
                        ],
                    },
                },
            },
            "included": [],
            "links": {},
        }


class TestCreate:
    def test_create(self, session: Session, setup_database: OneTimeData):
        earth_id = setup_database.earth_id

        milky_way = Galaxy(name="Milky Way")
        session.add(milky_way)
        session.commit()

        response = client.post(
            f"/stars",
            json={
                "data": {
                    "type": "star",
                    "attributes": {
                        "name": "Vega",
                        # This is a valid attribute, but is not included in Create, so
                        # should be ignored.
                        "color": "red",
                    },
                    "relationships": {
                        "galaxy": {"data": {"type": "galaxy", "id": str(milky_way.id)}},
                        "planets": {
                            "data": [
                                {"type": "planet", "id": str(earth_id)},
                            ]
                        },
                    },
                },
            },
        )

        # assert response.status_code == 201
        assert response.json() == {
            "data": {
                "type": "star",
                "id": IsStr,
                "attributes": {
                    "brightness": 1,
                    "name": "Vega",
                    "color": "",
                },
                "relationships": {
                    "galaxy": {
                        "data": {"type": "galaxy", "id": str(milky_way.id)},
                    },
                    "planets": {
                        "data": [
                            {"id": str(earth_id), "type": "planet"},
                        ],
                    },
                },
            },
            "included": [],
            "links": {},
        }


class TestDelete:
    def test_delete(self, session: Session):
        star = Star(name="Sirius")
        session.add(star)
        session.commit()

        response = client.delete(f"/stars/{star.id}")
        assert response.status_code == 204

        assert star not in session


class TestOptionalRelationships:
    def test_doesnt_include_relationship_if_on_the_read_model(self, session: Session):
        galaxy = Galaxy(name="Milky Way")
        session.add(galaxy)
        session.commit()

        response = client.get(f"/galaxys/{galaxy.id}")

        # This doesn't include the cluster, even though it's a relationship of the model.
        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "id": str(galaxy.id),
                "type": "galaxy",
                "attributes": {"name": "Milky Way"},
                "relationships": {
                    "favorite_planets": {
                        "data": [],
                    },
                    "stars": {
                        "data": [],
                    },
                },
            },
            "included": [],
            "links": {},
        }


class TestSchema:
    def test_include(self):
        schema = app.openapi()

        # Galaxy only has Star as a direct relationship, so the inclusion
        # of a planet shows the router is walking the relationships.
        assert (
            "GalaxyRead___planets__list__included__galaxy__Galaxy__Attributes"
            in schema["components"]["schemas"]
        )


class TestErrors:
    def test_validation_error(self):
        response = client.post(
            f"/stars",
            json={
                "data": {},
            },
        )

        assert response.status_code == 422
        assert response.json() == {
            "errors": [
                {
                    "code": "missing",
                    "source": "/body/data/type",
                    "status": 422,
                    "title": "Field required",
                },
            ]
        }

    def test_http_exception_error(self, session: Session, setup_database: OneTimeData):
        response = client.request(
            "get",
            f"/stars/123",
            json={
                "data": {},
            },
        )

        assert response.status_code == 404
        assert response.json() == {
            "errors": [
                {"code": "star not found", "status": 404, "title": "star not found"}
            ]
        }

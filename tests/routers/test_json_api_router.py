from pprint import pprint
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi_resources import routers
from sqlalchemy.orm.session import close_all_sessions
from sqlmodel import Session, select
from tests.resources.sqlmodel_models import (
    Galaxy,
    GalaxyResource,
    Planet,
    PlanetResource,
    Star,
    StarResource,
    engine,
    registry,
)

app = FastAPI()

planet_router = routers.JSONAPIResourceRouter(resource_class=PlanetResource)
star_router = routers.JSONAPIResourceRouter(resource_class=StarResource)
galaxy_router = routers.JSONAPIResourceRouter(resource_class=GalaxyResource)

app.include_router(planet_router)
app.include_router(star_router)
app.include_router(galaxy_router)


client = TestClient(app)


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

    # Patch the SQLResource's session
    def get_resource_kwargs(self: routers.JSONAPIResourceRouter, request: Request):
        return {"session": session}

    with patch.object(
        routers.JSONAPIResourceRouter, "get_resource_kwargs", get_resource_kwargs
    ):
        yield session

    session.close()
    transaction.rollback()
    conn.close()


class TestRetrieve:
    def test_retrieve(self, session: Session):
        star = Star(name="Sirius")
        planet = Planet(name="Earth", star=star)

        session.add(star)
        session.add(planet)
        session.commit()

        response = client.get(f"/stars/{star.id}")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "id": "1",
                "type": "star",
                "attributes": {"name": "Sirius", "brightness": 1},
                "links": {"self": "/stars/1"},
                "relationships": {
                    "planets": {
                        "data": [
                            {
                                "type": "planet",
                                "id": "1",
                            }
                        ],
                        "links": {
                            "related": "/stars/1/planets",
                            "self": "/stars/1/relationships/planets",
                        },
                    },
                    "galaxy": {
                        "data": None,
                        "links": {
                            "related": "/stars/1/galaxy",
                            "self": "/stars/1/relationships/galaxy",
                        },
                    },
                },
            },
            "included": [],
            "links": {"self": "/stars/1"},
        }

    def test_include(self, session: Session):
        star = Star(name="Sirius")
        planet = Planet(name="Earth", star=star)

        session.add(star)
        session.add(planet)
        session.commit()

        response = client.get(f"/planets/{planet.id}?include=star")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "id": "1",
                "attributes": {
                    "name": "Earth",
                },
                "type": "planet",
                "relationships": {
                    "favorite_galaxy": {
                        "data": None,
                        "links": {
                            "related": "/planets/1/favorite_galaxy",
                            "self": "/planets/1/relationships/favorite_galaxy",
                        },
                    },
                    "star": {
                        "data": {"type": "star", "id": "1"},
                        "links": {
                            "related": "/planets/1/star",
                            "self": "/planets/1/relationships/star",
                        },
                    },
                },
                "links": {"self": "/planets/1"},
            },
            "included": [
                {
                    "attributes": {"name": "Sirius", "brightness": 1},
                    "id": "1",
                    "type": "star",
                    "links": {"self": "/stars/1"},
                    "relationships": {
                        "galaxy": {
                            "data": None,
                            "links": {
                                "related": "/stars/1/galaxy",
                                "self": "/stars/1/relationships/galaxy",
                            },
                        },
                        "planets": {
                            "data": [
                                {
                                    "type": "planet",
                                    "id": "1",
                                }
                            ],
                            "links": {
                                "related": "/stars/1/planets",
                                "self": "/stars/1/relationships/planets",
                            },
                        },
                    },
                }
            ],
            "links": {"self": "/planets/1?include=star"},
        }


class TestList:
    def test_list(self, session: Session):
        star = Star(name="Sirius")

        session.add(star)
        session.commit()

        response = client.get(f"/stars")

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "attributes": {"name": "Sirius", "brightness": 1},
                    "id": "1",
                    "type": "star",
                    "links": {"self": "/stars/1"},
                    "relationships": {
                        "galaxy": {
                            "data": None,
                            "links": {
                                "related": "/stars/1/galaxy",
                                "self": "/stars/1/relationships/galaxy",
                            },
                        },
                        "planets": {
                            "data": [],
                            "links": {
                                "related": "/stars/1/planets",
                                "self": "/stars/1/relationships/planets",
                            },
                        },
                    },
                }
            ],
            "included": [],
            "links": {"self": "/stars"},
        }

    def test_include(self, session: Session):
        galaxy = Galaxy(name="Milky Way")
        star = Star(name="Sun", galaxy=galaxy)
        planet = Planet(name="Earth", star=star)
        hoth = Planet(name="Hoth")

        session.add(galaxy)
        session.add(star)
        session.add(planet)
        session.add(hoth)
        session.commit()

        response = client.get(f"/planets?include=star")

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "attributes": {
                        "name": "Earth",
                    },
                    "id": "1",
                    "type": "planet",
                    "links": {"self": "/planets/1"},
                    "relationships": {
                        "favorite_galaxy": {
                            "data": None,
                            "links": {
                                "related": "/planets/1/favorite_galaxy",
                                "self": "/planets/1/relationships/favorite_galaxy",
                            },
                        },
                        "star": {
                            "data": {"id": "1", "type": "star"},
                            "links": {
                                "related": "/planets/1/star",
                                "self": "/planets/1/relationships/star",
                            },
                        },
                    },
                },
                {
                    "attributes": {
                        "name": "Hoth",
                    },
                    "id": "2",
                    "type": "planet",
                    "links": {"self": "/planets/2"},
                    "relationships": {
                        "favorite_galaxy": {
                            "data": None,
                            "links": {
                                "related": "/planets/2/favorite_galaxy",
                                "self": "/planets/2/relationships/favorite_galaxy",
                            },
                        },
                        "star": {
                            "data": None,
                            "links": {
                                "related": "/planets/2/star",
                                "self": "/planets/2/relationships/star",
                            },
                        },
                    },
                },
            ],
            "included": [
                {
                    "attributes": {"name": "Sun", "brightness": 1},
                    "id": "1",
                    "type": "star",
                    "links": {"self": "/stars/1"},
                    "relationships": {
                        "galaxy": {
                            "data": {"type": "galaxy", "id": "1"},
                            "links": {
                                "related": "/stars/1/galaxy",
                                "self": "/stars/1/relationships/galaxy",
                            },
                        },
                        "planets": {
                            "data": [{"type": "planet", "id": "1"}],
                            "links": {
                                "related": "/stars/1/planets",
                                "self": "/stars/1/relationships/planets",
                            },
                        },
                    },
                }
            ],
            "links": {"self": "/planets?include=star"},
        }


class TestUpdate:
    def test_update(self, session: Session):
        star = Star(name="Sirius")
        galaxy = Galaxy(name="Milky Way")
        earth = Planet(name="Earth")
        mars = Planet(name="Mars")

        session.add(star)
        session.add(galaxy)
        session.add(earth)
        session.add(mars)
        session.commit()
        session.refresh(star)

        response = client.patch(
            f"/stars/{star.id}",
            json={
                "data": {
                    "type": "star",
                    "id": star.id,
                    "attributes": {
                        "name": "Vega",
                    },
                    "relationships": {
                        "galaxy": {"data": {"type": "galaxy", "id": galaxy.id}},
                        "planets": {
                            "data": [
                                {"type": "planet", "id": earth.id},
                                {"type": "planet", "id": mars.id},
                            ]
                        },
                    },
                }
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "attributes": {"name": "Vega", "brightness": 1},
                "id": "1",
                "type": "star",
                "links": {"self": "/stars/1"},
                "relationships": {
                    "galaxy": {
                        "data": {"type": "galaxy", "id": str(galaxy.id)},
                        "links": {
                            "related": "/stars/1/galaxy",
                            "self": "/stars/1/relationships/galaxy",
                        },
                    },
                    "planets": {
                        "data": [
                            {"id": str(earth.id), "type": "planet"},
                            {"id": str(mars.id), "type": "planet"},
                        ],
                        "links": {
                            "related": "/stars/1/planets",
                            "self": "/stars/1/relationships/planets",
                        },
                    },
                },
            },
            "included": [],
            "links": {"self": "/stars/1"},
        }


class TestCreate:
    def test_create(self, session: Session):
        response = client.post(f"/stars", json={"name": "Vega"})

        assert response.status_code == 201
        assert response.json() == {
            "data": {
                "attributes": {"name": "Vega", "brightness": 1},
                "id": "1",
                "type": "star",
                "links": {"self": "/stars/1"},
                "relationships": {
                    "galaxy": {
                        "data": None,
                        "links": {
                            "related": "/stars/1/galaxy",
                            "self": "/stars/1/relationships/galaxy",
                        },
                    },
                    "planets": {
                        "data": [],
                        "links": {
                            "related": "/stars/1/planets",
                            "self": "/stars/1/relationships/planets",
                        },
                    },
                },
            },
            "included": [],
            "links": {"self": "/stars"},
        }


class TestDelete:
    def test_delete(self, session: Session):
        star = Star(name="Sirius")
        session.add(star)
        session.commit()

        response = client.delete(f"/stars/{star.id}")
        assert response.status_code == 204

        assert star not in session


class TestSchema:
    def test_include(self):
        schema = app.openapi()

        # Galaxy only has Star as a direct relationship, so the inclusion
        # of a planet shows the router is walking the relationships.
        assert (
            "GalaxyRead___planets__list__included__galaxy__Galaxy__Attributes"
            in schema["components"]["schemas"]
        )

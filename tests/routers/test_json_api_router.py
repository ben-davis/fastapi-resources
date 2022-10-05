from unittest.mock import patch

import pytest
from dirty_equals import IsStr
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi_resources import routers
from sqlmodel import Session
from tests.conftest import OneTimeData
from tests.resources.sqlmodel_models import (
    Galaxy,
    GalaxyResource,
    Planet,
    PlanetResource,
    Star,
    StarResource,
    engine,
)

app = FastAPI()

planet_router = routers.JSONAPIResourceRouter(resource_class=PlanetResource)
star_router = routers.JSONAPIResourceRouter(resource_class=StarResource)
galaxy_router = routers.JSONAPIResourceRouter(resource_class=GalaxyResource)

app.include_router(planet_router)
app.include_router(star_router)
app.include_router(galaxy_router)


client = TestClient(app)


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
    def test_retrieve(self, session: Session, setup_database: OneTimeData):
        sun_id, earth_id = setup_database

        response = client.get(f"/stars/{sun_id}")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "id": str(sun_id),
                "type": "star",
                "attributes": {"name": "Sun", "brightness": 1},
                "links": {"self": f"/stars/{sun_id}"},
                "relationships": {
                    "planets": {
                        "data": [
                            {
                                "type": "planet",
                                "id": str(earth_id),
                            }
                        ],
                        "links": {
                            "related": f"/stars/{sun_id}/planets",
                            "self": f"/stars/{sun_id}/relationships/planets",
                        },
                    },
                    "galaxy": {
                        "data": None,
                        "links": {
                            "related": f"/stars/{sun_id}/galaxy",
                            "self": f"/stars/{sun_id}/relationships/galaxy",
                        },
                    },
                },
            },
            "included": [],
            "links": {"self": f"/stars/{sun_id}"},
        }

    def test_include(self, session: Session, setup_database: OneTimeData):
        sun_id, earth_id = setup_database

        response = client.get(f"/planets/{earth_id}?include=star")

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
                            "related": f"/planets/{earth_id}/favorite_galaxy",
                            "self": f"/planets/{earth_id}/relationships/favorite_galaxy",
                        },
                    },
                    "star": {
                        "data": {"type": "star", "id": "1"},
                        "links": {
                            "related": f"/planets/{earth_id}/star",
                            "self": f"/planets/{earth_id}/relationships/star",
                        },
                    },
                },
                "links": {"self": f"/planets/{earth_id}"},
            },
            "included": [
                {
                    "id": str(sun_id),
                    "type": "star",
                    "attributes": {"name": "Sun", "brightness": 1},
                    "links": {"self": f"/stars/{sun_id}"},
                    "relationships": {
                        "planets": {
                            "data": [
                                {
                                    "type": "planet",
                                    "id": str(earth_id),
                                }
                            ],
                            "links": {
                                "related": f"/stars/{sun_id}/planets",
                                "self": f"/stars/{sun_id}/relationships/planets",
                            },
                        },
                        "galaxy": {
                            "data": None,
                            "links": {
                                "related": f"/stars/{sun_id}/galaxy",
                                "self": f"/stars/{sun_id}/relationships/galaxy",
                            },
                        },
                    },
                }
            ],
            "links": {"self": f"/planets/{earth_id}?include=star"},
        }


class TestList:
    def test_list(self, session: Session, setup_database: OneTimeData):
        response = client.get(f"/stars")

        sun_id, earth_id = setup_database

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "id": str(sun_id),
                    "type": "star",
                    "attributes": {"name": "Sun", "brightness": 1},
                    "links": {"self": f"/stars/{sun_id}"},
                    "relationships": {
                        "planets": {
                            "data": [
                                {
                                    "type": "planet",
                                    "id": str(earth_id),
                                }
                            ],
                            "links": {
                                "related": f"/stars/{sun_id}/planets",
                                "self": f"/stars/{sun_id}/relationships/planets",
                            },
                        },
                        "galaxy": {
                            "data": None,
                            "links": {
                                "related": f"/stars/{sun_id}/galaxy",
                                "self": f"/stars/{sun_id}/relationships/galaxy",
                            },
                        },
                    },
                }
            ],
            "included": [],
            "links": {"self": "/stars"},
        }

    def test_include(self, session: Session, setup_database: OneTimeData):
        sun_id, earth_id = setup_database

        # Add a planet with a new star and a galaxy, so we can test it still works even if
        # not all objects have the inclusion (so the OneTimeData star doesn't have a galaxy).
        star_wars_galaxy = Galaxy(name="Far Far Away")
        priate = Star(name="Priate", galaxy=star_wars_galaxy)
        mustafar = Planet(name="Mustafar", star=priate)

        # Add another planet with the OneTimeData star, so we can test inclusion are de-duped.
        mars = Planet(name="Mars", star_id=sun_id)

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
                    "links": {"self": f"/planets/{earth_id}"},
                    "relationships": {
                        "favorite_galaxy": {
                            "data": None,
                            "links": {
                                "related": f"/planets/{earth_id}/favorite_galaxy",
                                "self": f"/planets/{earth_id}/relationships/favorite_galaxy",
                            },
                        },
                        "star": {
                            "data": {"id": str(sun_id), "type": "star"},
                            "links": {
                                "related": f"/planets/{earth_id}/star",
                                "self": f"/planets/{earth_id}/relationships/star",
                            },
                        },
                    },
                },
                {
                    "attributes": {
                        "name": "Mustafar",
                    },
                    "id": "2",
                    "type": "planet",
                    "links": {"self": f"/planets/{mustafar.id}"},
                    "relationships": {
                        "favorite_galaxy": {
                            "data": None,
                            "links": {
                                "related": f"/planets/{mustafar.id}/favorite_galaxy",
                                "self": f"/planets/{mustafar.id}/relationships/favorite_galaxy",
                            },
                        },
                        "star": {
                            "data": {"id": str(priate.id), "type": "star"},
                            "links": {
                                "related": f"/planets/{mustafar.id}/star",
                                "self": f"/planets/{mustafar.id}/relationships/star",
                            },
                        },
                    },
                },
                {
                    "attributes": {
                        "name": "Mars",
                    },
                    "id": str(mars.id),
                    "type": "planet",
                    "links": {"self": f"/planets/{mars.id}"},
                    "relationships": {
                        "favorite_galaxy": {
                            "data": None,
                            "links": {
                                "related": f"/planets/{mars.id}/favorite_galaxy",
                                "self": f"/planets/{mars.id}/relationships/favorite_galaxy",
                            },
                        },
                        "star": {
                            "data": {"id": str(sun_id), "type": "star"},
                            "links": {
                                "related": f"/planets/{mars.id}/star",
                                "self": f"/planets/{mars.id}/relationships/star",
                            },
                        },
                    },
                },
            ],
            "included": [
                {
                    "attributes": {"name": "Sun", "brightness": 1},
                    "id": str(sun_id),
                    "type": "star",
                    "links": {"self": f"/stars/{sun_id}"},
                    "relationships": {
                        "galaxy": {
                            "data": None,
                            "links": {
                                "related": f"/stars/{sun_id}/galaxy",
                                "self": f"/stars/{sun_id}/relationships/galaxy",
                            },
                        },
                        "planets": {
                            "data": [
                                {"type": "planet", "id": str(earth_id)},
                                {"type": "planet", "id": str(mars.id)},
                            ],
                            "links": {
                                "related": f"/stars/{sun_id}/planets",
                                "self": f"/stars/{sun_id}/relationships/planets",
                            },
                        },
                    },
                },
                {
                    "attributes": {"name": "Priate", "brightness": 1},
                    "id": str(priate.id),
                    "type": "star",
                    "links": {"self": f"/stars/{priate.id}"},
                    "relationships": {
                        "galaxy": {
                            "data": {"type": "galaxy", "id": "1"},
                            "links": {
                                "related": f"/stars/{priate.id}/galaxy",
                                "self": f"/stars/{priate.id}/relationships/galaxy",
                            },
                        },
                        "planets": {
                            "data": [{"type": "planet", "id": str(mustafar.id)}],
                            "links": {
                                "related": f"/stars/{priate.id}/planets",
                                "self": f"/stars/{priate.id}/relationships/planets",
                            },
                        },
                    },
                },
                {
                    "attributes": {"name": "Far Far Away"},
                    "id": str(star_wars_galaxy.id),
                    "type": "galaxy",
                    "links": {"self": f"/galaxys/{star_wars_galaxy.id}"},
                    "relationships": {
                        "stars": {
                            "data": [{"type": "star", "id": str(priate.id)}],
                            "links": {
                                "related": f"/galaxys/{star_wars_galaxy.id}/stars",
                                "self": f"/galaxys/{star_wars_galaxy.id}/relationships/stars",
                            },
                        },
                        "favorite_planets": {
                            "data": [],
                            "links": {
                                "related": f"/galaxys/{star_wars_galaxy.id}/favorite_planets",
                                "self": f"/galaxys/{star_wars_galaxy.id}/relationships/favorite_planets",
                            },
                        },
                    },
                },
            ],
            "links": {"self": "/planets?include=star.galaxy"},
        }


class TestUpdate:
    def test_update(self, session: Session, setup_database: OneTimeData):
        sun_id, _ = setup_database

        galaxy = Galaxy(name="Milky Way")
        mercury = Planet(name="Mercury")
        jupiter = Planet(name="Jupiter")

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
                    },
                    "relationships": {
                        "galaxy": {"data": {"type": "galaxy", "id": galaxy.id}},
                        "planets": {
                            "data": [
                                {"type": "planet", "id": mercury.id},
                                {"type": "planet", "id": jupiter.id},
                            ]
                        },
                    },
                }
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "attributes": {"name": "Suntastic", "brightness": 1},
                "id": str(sun_id),
                "type": "star",
                "links": {"self": f"/stars/{sun_id}"},
                "relationships": {
                    "galaxy": {
                        "data": {"type": "galaxy", "id": str(galaxy.id)},
                        "links": {
                            "related": f"/stars/{sun_id}/galaxy",
                            "self": f"/stars/{sun_id}/relationships/galaxy",
                        },
                    },
                    "planets": {
                        "data": [
                            {"id": str(mercury.id), "type": "planet"},
                            {"id": str(jupiter.id), "type": "planet"},
                        ],
                        "links": {
                            "related": f"/stars/{sun_id}/planets",
                            "self": f"/stars/{sun_id}/relationships/planets",
                        },
                    },
                },
            },
            "included": [],
            "links": {"self": f"/stars/{sun_id}"},
        }


class TestCreate:
    def test_create(self, session: Session):
        response = client.post(f"/stars", json={"name": "Vega"})

        assert response.status_code == 201
        assert response.json() == {
            "data": {
                "attributes": {"name": "Vega", "brightness": 1},
                "id": IsStr,
                "type": "star",
                "links": {"self": IsStr},
                "relationships": {
                    "galaxy": {
                        "data": None,
                        "links": {
                            "related": IsStr,
                            "self": IsStr,
                        },
                    },
                    "planets": {
                        "data": [],
                        "links": {
                            "related": IsStr,
                            "self": IsStr,
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

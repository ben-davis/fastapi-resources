import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_resources import routers
from tests.resources.sqlmodel_models import Planet
from tests.routers import in_memory_resource
from tests.routers.models import (
    Galaxy,
    GalaxyResource,
    PlanetResource,
    Star,
    StarResource,
)

app = FastAPI()

planet_router = routers.JSONAPIResourceRouter(resource_class=PlanetResource)
star_router = routers.JSONAPIResourceRouter(resource_class=StarResource)
galaxy_router = routers.JSONAPIResourceRouter(resource_class=GalaxyResource)

app.include_router(planet_router)
app.include_router(star_router)
app.include_router(galaxy_router)


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    in_memory_resource.id_counter = 1
    in_memory_resource.test_db["galaxy"] = {}
    in_memory_resource.test_db["star"] = {}
    in_memory_resource.test_db["planet"] = {}


class TestRetrieve:
    def test_retrieve(self):
        star = Star(name="Sirius")
        star.id = 1
        planet = Planet(name="Earth", star_id=1)
        planet.id = 1

        in_memory_resource.test_db["planet"][planet.id] = planet
        in_memory_resource.test_db["star"][star.id] = star

        response = client.get(f"/stars/{star.id}")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "id": "1",
                "type": "star",
                "attributes": {"name": "Sirius"},
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

    def test_include(self):
        star = Star(name="Sun")
        star.id = 1
        planet = Planet(name="Earth", star_id=1)
        planet.id = 1

        in_memory_resource.test_db["star"][star.id] = star
        in_memory_resource.test_db["planet"][planet.id] = planet

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
                    "star": {
                        "data": {"type": "star", "id": "1"},
                        "links": {
                            "related": "/planets/1/star",
                            "self": "/planets/1/relationships/star",
                        },
                    }
                },
                "links": {"self": "/planets/1"},
            },
            "included": [
                {
                    "attributes": {"name": "Sun"},
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
    def test_list(self):
        star = Star(name="Sirius")
        star.id = 1

        in_memory_resource.test_db["star"][star.id] = star

        response = client.get(f"/stars")

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "attributes": {"name": "Sirius"},
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

    def test_include(self):
        galaxy = Galaxy(name="Milky Way")
        galaxy.id = 1
        star = Star(name="Sun", galaxy_id=1)
        star.id = 1
        planet = Planet(name="Earth", star_id=1)
        planet.id = 1
        hoth = Planet(name="Hoth")
        hoth.id = 2

        in_memory_resource.test_db["galaxy"][galaxy.id] = galaxy
        in_memory_resource.test_db["star"][star.id] = star
        in_memory_resource.test_db["planet"][planet.id] = planet
        in_memory_resource.test_db["planet"][hoth.id] = hoth

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
                    "attributes": {"name": "Sun"},
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
    def test_update(self):
        star = Star(name="Sirius")
        star.id = 1

        in_memory_resource.test_db["star"][star.id] = star

        # TODO: Correct the patch
        response = client.patch(
            f"/stars/{star.id}",
            json={
                "data": {
                    "type": "star",
                    "id": star.id,
                    "attributes": {
                        "name": "Vega",
                    },
                }
            },
        )

        assert response.json() == ""
        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "attributes": {"name": "Vega"},
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
            "links": {"self": "/stars/1"},
        }

        assert in_memory_resource.test_db["star"][1].name == "Vega"


class TestCreate:
    def test_create(self):
        response = client.post(f"/stars", json={"name": "Vega"})

        assert response.status_code == 201
        assert response.json() == {
            "data": {
                "attributes": {"name": "Vega"},
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

        assert in_memory_resource.test_db["star"][1]


class TestDelete:
    def test_delete(self):
        star = Star(name="Sirius")
        star.id = 1

        in_memory_resource.test_db["star"][star.id] = star

        response = client.delete(f"/stars/{star.id}")
        assert response.status_code == 204

        assert not in_memory_resource.test_db["star"]


class TestSchema:
    def test_include(self):
        schema = app.openapi()
        galaxy_included = [
            item["$ref"]
            for item in schema["components"]["schemas"][
                "JAResponseSingle_GalaxyRead__Literal__List_"
            ]["properties"]["included"]["items"]["anyOf"]
        ]

        # Galaxy only has Star as a direct relationship, so the inclusion
        # of a planet shows the router is walking the relationships.
        assert galaxy_included == [
            "#/components/schemas/JAResourceObject_Star__Literal_",
            "#/components/schemas/JAResourceObject_Planet__Literal_",
        ]

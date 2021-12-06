from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Field, Relationship, SQLModel

from fastapi_rest_framework import routers
from tests import in_memory_resource


class PlanetBase(SQLModel):
    name: str

    star_id: Optional[int] = Field(default=None, foreign_key="star.id")


class Planet(PlanetBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    star: "Star" = Relationship(back_populates="planets")


class PlanetCreate(PlanetBase):
    pass


class PlanetRead(PlanetBase):
    id: int


class PlanetUpdate(SQLModel):
    id: Optional[int] = None
    name: Optional[str] = None


class StarBase(SQLModel):
    name: str


class Star(StarBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    planets: Planet = Relationship(back_populates="star")


class StarCreate(StarBase):
    pass


class StarRead(StarBase):
    id: int


class StarUpdate(SQLModel):
    id: Optional[int] = None
    name: Optional[str] = None


class PlanetResource(in_memory_resource.InMemorySQLModelResource):
    name = "planet"
    Db = Planet
    Read = PlanetRead
    Create = PlanetCreate
    Update = PlanetUpdate


class StarResource(in_memory_resource.InMemorySQLModelResource):
    name = "star"
    Db = Star
    Read = StarRead
    Create = StarCreate
    Update = StarUpdate


app = FastAPI()

planet = routers.JSONAPIResourceRouter(prefix="/planets", resource_class=PlanetResource)

star = routers.JSONAPIResourceRouter(prefix="/stars", resource_class=StarResource)

app.include_router(planet)
app.include_router(star)


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    in_memory_resource.test_db["star"] = {}
    in_memory_resource.test_db["planet"] = {}


class TestRetrieve:
    def test_retrieve(self):
        star = StarRead(name="Sirius", id=1)

        in_memory_resource.test_db["star"][star.id] = star

        response = client.get(f"/stars/{star.id}")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "attributes": {"id": 1, "name": "Sirius"},
                "id": "1",
                "type": "star",
            },
            "included": [],
        }

    def test_include(self):
        star = StarRead(name="Sun", id=1)
        planet = PlanetRead(name="Earth", id=1, star_id=1)

        in_memory_resource.test_db["star"][star.id] = star
        in_memory_resource.test_db["planet"][planet.id] = planet

        response = client.get(f"/planets/{planet.id}?include=star")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "attributes": {"id": 1, "name": "Earth", "star_id": 1},
                "id": "1",
                "type": "planet",
            },
            "included": [
                {
                    "attributes": {"id": 1, "name": "Sun"},
                    "id": "1",
                    "type": "star",
                }
            ],
        }


class TestList:
    def test_list(self):
        star = StarRead(name="Sirius", id=1)

        in_memory_resource.test_db["star"][star.id] = star

        response = client.get(f"/stars/")

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "attributes": {"id": 1, "name": "Sirius"},
                    "id": "1",
                    "type": "star",
                }
            ],
            "included": [],
        }

    def test_include(self):
        star = StarRead(name="Sun", id=1)
        planet = PlanetRead(name="Earth", id=1, star_id=1)
        hoth = PlanetRead(name="Hoth", id=2)

        in_memory_resource.test_db["star"][star.id] = star
        in_memory_resource.test_db["planet"][planet.id] = planet
        in_memory_resource.test_db["planet"][hoth.id] = hoth

        response = client.get(f"/planets/?include=star")

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "attributes": {"id": 1, "name": "Earth", "star_id": 1},
                    "id": "1",
                    "type": "planet",
                },
                {
                    "attributes": {"id": 2, "name": "Hoth", "star_id": None},
                    "id": "2",
                    "type": "planet",
                },
            ],
            "included": [
                {
                    "attributes": {"id": 1, "name": "Sun"},
                    "id": "1",
                    "type": "star",
                }
            ],
        }


class TestUpdate:
    def test_update(self):
        star = StarRead(name="Sirius", id=1)

        in_memory_resource.test_db["star"][star.id] = star

        response = client.patch(f"/stars/{star.id}", json={"name": "Vega"})

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "attributes": {"id": 1, "name": "Vega"},
                "id": "1",
                "type": "star",
            },
            "included": [],
        }

        assert in_memory_resource.test_db["star"][1].name == "Vega"


class TestCreate:
    def test_create(self):
        response = client.post(f"/stars/", json={"name": "Vega"})

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "attributes": {"id": 1, "name": "Vega"},
                "id": "1",
                "type": "star",
            },
            "included": [],
        }

        assert in_memory_resource.test_db["star"][1]


class TestDelete:
    def test_delete(self):
        star = StarRead(name="Sirius", id=1)

        in_memory_resource.test_db["star"][star.id] = star

        response = client.delete(f"/stars/{star.id}")
        assert response.status_code == 204


        assert not in_memory_resource.test_db["star"]

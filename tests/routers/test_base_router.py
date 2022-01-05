from typing import Generic, TypeVar

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic.generics import GenericModel

from fastapi_rest_framework import routers
from fastapi_rest_framework.routers import decorators
from tests.routers import in_memory_resource
from tests.routers.models import (
    Galaxy,
    GalaxyResource,
    GalaxyUpdate,
    PlanetResource,
    Star,
    StarResource,
)

app = FastAPI()

planet_router = routers.ResourceRouter(prefix="/planets", resource_class=PlanetResource)
star_router = routers.ResourceRouter(prefix="/stars", resource_class=StarResource)


T = TypeVar("T")


class Envelope(GenericModel, Generic[T]):
    data: T


class GalaxyResourceRouter(routers.ResourceRouter[GalaxyResource]):
    # Envelope the response so we can check that actions call build_respone
    def build_response(self, resource, rows):
        data = super().build_response(resource, rows)
        return {"data": data}

    def get_read_response_model(self):
        model = super().get_read_response_model()
        return Envelope[model]

    def get_list_response_model(self):
        model = super().get_list_response_model()
        return Envelope[model]

    @decorators.action(detail=False)
    def distant_galaxies(self, request: Request):
        resource = self.get_resource(request=request)
        return resource.list()

    @decorators.action(detail=True, methods=["patch"])
    def rename(self, id: int, request: Request):
        resource = self.get_resource(request=request)
        obj = resource.update(id=id, model=GalaxyUpdate(name="Andromeda"))
        return obj


galaxy_router = GalaxyResourceRouter(prefix="/galaxies", resource_class=GalaxyResource)

app.include_router(planet_router)
app.include_router(star_router)
app.include_router(galaxy_router)


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    in_memory_resource.test_db["galaxy"] = {}
    in_memory_resource.test_db["star"] = {}
    in_memory_resource.test_db["planet"] = {}


class TestRetrieve:
    def test_retrieve(self):
        star = Star(name="Sirius")
        star.id = 1

        in_memory_resource.test_db["star"][star.id] = star

        response = client.get(f"/stars/{star.id}")

        assert response.status_code == 200
        assert response.json() == {
            "id": 1,
            "name": "Sirius",
            "galaxy_id": None,
        }


class TestList:
    def test_list(self):
        star = Star(name="Sirius")
        star.id = 1

        in_memory_resource.test_db["star"][star.id] = star

        response = client.get(f"/stars/")

        assert response.status_code == 200
        assert response.json() == [
            {"id": 1, "name": "Sirius", "galaxy_id": None},
        ]


class TestUpdate:
    def test_update(self):
        star = Star(name="Sirius")
        star.id = 1

        in_memory_resource.test_db["star"][star.id] = star

        response = client.patch(f"/stars/{star.id}", json={"name": "Vega"})

        assert response.status_code == 200
        assert response.json() == {"id": 1, "name": "Vega", "galaxy_id": None}

        assert in_memory_resource.test_db["star"][1].name == "Vega"


class TestCreate:
    def test_create(self):
        response = client.post(f"/stars/", json={"name": "Vega"})

        assert response.status_code == 200
        assert response.json() == {
            "id": 1,
            "name": "Vega",
            "galaxy_id": None,
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


class TestActions:
    def test_list(self):
        galaxy = Galaxy(name="Milky Way")
        galaxy.id = 1

        in_memory_resource.test_db["galaxy"][galaxy.id] = galaxy

        response = client.get("/galaxies/distant_galaxies")
        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {"id": 1, "name": "Milky Way"},
            ]
        }

    def test_update(self):
        galaxy = Galaxy(name="Milky Way")
        galaxy.id = 1

        in_memory_resource.test_db["galaxy"][galaxy.id] = galaxy

        response = client.patch(f"/galaxies/{galaxy.id}/rename")
        assert response.status_code == 200
        assert response.json() == {"data": {"id": 1, "name": "Andromeda"}}

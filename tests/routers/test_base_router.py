from typing import Generic, TypeVar
from unittest import mock

import pytest
from dirty_equals import IsInt
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic.generics import GenericModel
from sqlmodel import Session

from fastapi_resources import routers
from fastapi_resources.routers import decorators
from tests.conftest import OneTimeData
from tests.resources.sqlmodel_models import (
    Galaxy,
    GalaxyCreate,
    GalaxyResource,
    PlanetResource,
    Star,
    StarResource,
    engine,
)

app = FastAPI()

planet_router = routers.ResourceRouter(prefix="/planets", resource_class=PlanetResource)
star_router = routers.ResourceRouter(prefix="/stars", resource_class=StarResource)


T = TypeVar("T")


class Envelope(GenericModel, Generic[T]):
    data: T


class FakeJobs:
    @staticmethod
    def do_something():
        pass


class GalaxyResourceRouter(routers.ResourceRouter[GalaxyResource]):
    # Envelope the response so we can check that actions call build_response
    def build_response(self, resource, rows, request):
        data = super().build_response(resource, rows, request)
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
        obj = resource.update(id=id, attributes={"name": "Andromeda"})
        return obj

    def perform_update(
        self,
        request: Request,
        resource: GalaxyResource,
        id: int,
        attributes: dict,
        relationships: dict,
    ):
        attributes["name"] = "ProvidedByPerformUpdate"
        return resource.update(
            id=id, attributes=attributes, relationships=relationships
        )

    def perform_create(
        self,
        request: Request,
        resource: GalaxyResource,
        attributes: dict,
        relationships: dict,
    ):
        attributes["name"] = "ProvidedByPerformCreate"
        return resource.create(attributes=attributes, relationships=relationships)

    def perform_delete(self, request: Request, resource: GalaxyResource, id: int):
        FakeJobs.do_something()
        return resource.delete(id=id)


galaxy_router = GalaxyResourceRouter(prefix="/galaxies", resource_class=GalaxyResource)

app.include_router(planet_router)
app.include_router(star_router)
app.include_router(galaxy_router)


client = TestClient(app)


@pytest.fixture(scope="session")
def session():
    conn = engine.connect()
    transaction = conn.begin()
    session = Session(bind=conn)

    original_get_resource_kwargs = routers.ResourceRouter.get_resource_kwargs

    # Patch the SQLResource's session
    def get_resource_kwargs(self: routers.ResourceRouter, request: Request):
        return {
            **original_get_resource_kwargs(self=self, request=request),
            "session": session,
        }

    with mock.patch.object(
        routers.ResourceRouter, "get_resource_kwargs", get_resource_kwargs
    ):
        yield session

    session.close()
    transaction.rollback()
    conn.close()


class TestRetrieve:
    def test_retrieve(self, session: Session, setup_database: OneTimeData):
        sun_id = setup_database.sun_id

        response = client.get(f"/stars/{sun_id}")

        assert response.status_code == 200
        assert response.json() == {
            "id": sun_id,
            "name": "Sun",
            "brightness": 1,
            "color": "",
        }


class TestList:
    def test_list(self, session: Session, setup_database: OneTimeData):
        response = client.get(f"/stars/")

        assert response.status_code == 200
        assert response.json() == [
            {"id": setup_database.sun_id, "name": "Sun", "brightness": 1, "color": ""},
        ]


class TestUpdate:
    def test_update(self, session: Session):
        star = Star(name="Sirius")
        session.add(star)
        session.commit()

        response = client.patch(f"/stars/{star.id}", json={"name": "Vega"})

        assert response.status_code == 200
        assert response.json() == {
            "id": star.id,
            "name": "Vega",
            "brightness": 1,
            "color": "",
        }


class TestCreate:
    def test_create(self, session: Session):
        response = client.post(f"/stars", json={"name": "Vega"})

        assert response.status_code == 201
        assert response.json() == {
            "id": IsInt,
            "name": "Vega",
            "brightness": 1,
            "color": "",
        }


class TestDelete:
    def test_delete(self, session: Session):
        star = Star(name="Sirius")
        session.add(star)
        session.commit()

        response = client.delete(f"/stars/{star.id}")
        assert response.status_code == 204

        assert star not in session


class TestActions:
    def test_list(self, session: Session):
        galaxy = Galaxy(name="Milky Way")
        session.add(galaxy)
        session.commit()

        response = client.get("/galaxies/distant_galaxies")
        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {"id": 1, "name": "Milky Way"},
            ]
        }

    def test_update(self, session: Session):
        galaxy = Galaxy(name="Milky Way")
        session.add(galaxy)
        session.commit()

        response = client.patch(f"/galaxies/{galaxy.id}/rename")
        assert response.status_code == 200
        assert response.json() == {"data": {"id": galaxy.id, "name": "Andromeda"}}


class TestPerformHooks:
    def test_perform_create(self, session: Session):
        response = client.post(f"/galaxies", json={"name": "will be ignored"})

        assert response.status_code == 201
        assert response.json()["data"]["name"] == "ProvidedByPerformCreate"

    def test_perform_update(self, session: Session):
        galaxy = Galaxy(name="Milky Way")
        session.add(galaxy)
        session.commit()

        response = client.patch(
            f"/galaxies/{galaxy.id}", json={"name": "will be ignored"}
        )

        assert response.status_code == 200
        assert response.json() == {
            "data": {"id": galaxy.id, "name": "ProvidedByPerformUpdate"}
        }

    def test_perform_delete(self, session: Session):
        galaxy = Galaxy(name="Milky Way")
        session.add(galaxy)
        session.commit()

        with mock.patch.object(FakeJobs, "do_something") as patched_fake_job:
            response = client.delete(f"/galaxies/{galaxy.id}")

            assert response.status_code == 204
            patched_fake_job.assert_called_once()

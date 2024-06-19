from dataclasses import dataclass
from unittest.mock import patch

import pytest
from dirty_equals import IsPartialDict
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi_resources import routers
from fastapi_resources.resources import base_resource
from fastapi_resources.resources.types import (
    RelationshipInfo,
    Relationships,
    SchemaWithRelationships,
)
from tests.conftest import OneTimeData
from tests.resources.sqlalchemy_models import (
    AsteroidResource,
    GalaxyResource,
    PlanetResource,
    StarResource,
    engine,
)

app = FastAPI()


@dataclass
class Ship:
    id: str


class ShipRead(BaseModel):
    id: str


@dataclass
class Fleet:
    id: str
    ships: list[Ship]


class FleetRead(BaseModel):
    id: str

    __relationships__ = ["ships"]


class ShipResource(base_resource.Resource[Ship]):
    name = "ship"

    Db = Ship
    Read = ShipRead

    # TODO: Update fastapi-resources so we don't need to do this
    Create = None
    Update = None
    retrieve = None
    create = None
    update = None
    delete = None


class FleetResource(base_resource.Resource[Fleet]):
    name = "fleet"

    Db = Fleet
    Read = FleetRead

    # TODO: Update fastapi-resources so we don't need to do this
    Create = None
    Update = None
    retrieve = None
    create = None
    update = None
    delete = None

    @classmethod
    def get_relationships(cls) -> Relationships:
        ship_relationship = ShipResource.get_relationships()

        return {
            "ships": RelationshipInfo(
                schema_with_relationships=SchemaWithRelationships(
                    schema=Ship,
                    relationships=ship_relationship,
                ),
                many=True,
                field="ships",
            ),
        }

    def list(self):
        ship = Ship(id="1")
        fleet = Fleet(id="1", ships=[(ship, {"is_cool": True})])

        return (
            [(fleet, {"has_ships": True})],
            None,
            1,
        )


fleet_router = routers.JSONAPIResourceRouter(resource_class=FleetResource)
app.include_router(fleet_router)


client = TestClient(app)


class TestWithMeta:
    def test_retrieve(self):
        response = client.get(f"/fleets/?include=ships")

        assert response.status_code == 200
        assert response.json() == {
            "data": [IsPartialDict(type="fleet", meta={"has_ships": True})],
            "included": [IsPartialDict(type="ship", meta={"is_cool": True})],
            "links": {},
            "meta": {"count": 1},
        }

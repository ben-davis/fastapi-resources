from typing import List, Optional

from sqlalchemy.orm import registry as sa_registry
from sqlmodel import Field, Relationship, SQLModel, create_engine

from fastapi_rest_framework.resources import SQLModelResource

registry = sa_registry()

sqlite_url = f"sqlite://"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


class PlanetBase(SQLModel, registry=registry):
    name: str

    star_id: Optional[int] = Field(default=None, foreign_key="star.id")
    favorite_galaxy_id: Optional[int] = Field(default=None, foreign_key="galaxy.id")


class Planet(PlanetBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    star: "Star" = Relationship(back_populates="planets")
    favorite_galaxy: "Galaxy" = Relationship(back_populates="favorite_planets")


class PlanetCreate(PlanetBase):
    pass


class PlanetRead(PlanetBase):
    id: int


class PlanetUpdate(SQLModel, registry=registry):
    name: Optional[str] = None


class StarBase(SQLModel, registry=registry):
    name: str

    galaxy_id: Optional[int] = Field(default=None, foreign_key="galaxy.id")


class Star(StarBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    planets: List[Planet] = Relationship(back_populates="star")
    galaxy: "Galaxy" = Relationship(back_populates="stars")


class StarCreate(StarBase):
    pass


class StarRead(StarBase):
    id: int


class StarUpdate(SQLModel, registry=registry):
    name: Optional[str] = None


class GalaxyBase(SQLModel, registry=registry):
    name: str


class Galaxy(GalaxyBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    stars: List[Star] = Relationship(back_populates="galaxy")
    favorite_planets: List[Planet] = Relationship(back_populates="favorite_galaxy")


class GalaxyCreate(GalaxyBase):
    pass


class GalaxyRead(GalaxyBase):
    id: int


class GalaxyUpdate(SQLModel, registry=registry):
    name: Optional[str] = None


class PlanetResource(SQLModelResource):
    engine = engine
    name = "planet"
    Db = Planet
    Read = PlanetRead
    Create = PlanetCreate
    Update = PlanetUpdate


class StarResource(SQLModelResource[Star]):
    engine = engine
    name = "star"
    Db = Star
    Read = StarRead
    Create = StarCreate
    Update = StarUpdate


class GalaxyResource(SQLModelResource[Galaxy]):
    engine = engine
    name = "galaxy"
    Db = Galaxy
    Read = GalaxyRead
    Create = GalaxyCreate
    Update = GalaxyUpdate

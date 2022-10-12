from typing import List, Optional

from fastapi_resources.resources import SQLModelResource
from sqlmodel import Field, Relationship, SQLModel, create_engine

from .planet import Planet, PlanetCreate, PlanetRead, PlanetUpdate

sqlite_url = "sqlite+pysqlite://"
engine = create_engine(
    sqlite_url, connect_args={"check_same_thread": False}, future=True
)


class StarBase(SQLModel):
    name: str
    brightness: int = 1

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


class StarUpdate(SQLModel):
    name: Optional[str] = None
    brightness: Optional[int] = None


class GalaxyBase(SQLModel):
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


class GalaxyUpdate(SQLModel):
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

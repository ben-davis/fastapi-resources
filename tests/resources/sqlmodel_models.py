from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel, create_engine

from fastapi_resources.resources import SQLModelResource

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


class StarRead(SQLModel):
    id: int
    name: str
    brightness: int = 1
    planets: List[Planet] = Relationship(back_populates="star")
    galaxy: "Galaxy" = Relationship(back_populates="stars")


class StarUpdate(SQLModel):
    name: Optional[str] = None
    brightness: Optional[int] = None


class Cluster(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class GalaxyBase(SQLModel):
    name: str


class Galaxy(GalaxyBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    stars: List[Star] = Relationship(back_populates="galaxy")
    favorite_planets: List[Planet] = Relationship(back_populates="favorite_galaxy")

    cluster_id: Optional[int] = Field(default=None, foreign_key="cluster.id")
    cluster: Optional[Cluster] = Relationship()


class GalaxyCreate(GalaxyBase):
    pass


class GalaxyRead(GalaxyBase):
    id: int
    name: str

    stars: List[Star] = Relationship(back_populates="galaxy")
    favorite_planets: List[Planet] = Relationship(back_populates="favorite_galaxy")


class GalaxyUpdate(SQLModel):
    name: Optional[str] = None


class Moon(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    planet_id: int = Field(foreign_key="planet.id")
    planet: Planet = Relationship()


class MoonRead(SQLModel):
    id: int
    name: str
    planet: Planet = Relationship()


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


class MoonResource(SQLModelResource[Moon]):
    engine = engine
    name = "moon"
    Db = Moon
    Read = MoonRead

from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)

from fastapi_resources.resources import SQLAlchemyResource
from fastapi_resources.resources.sqlalchemy import paginators
from tests.resources.sqlalchemy_base import Base

from .planet import Planet, PlanetCreate, PlanetRead

# from sqlmodel import Field, Relationship, BaseModel, create_engine


sqlite_url = "sqlite+pysqlite://"
engine = create_engine(
    sqlite_url, connect_args={"check_same_thread": False}, future=True
)


class Star(Base):
    __tablename__ = "star"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str]
    color: Mapped[str] = mapped_column(default="")
    brightness: Mapped[int] = mapped_column(default=1)

    planets: Mapped[list[Planet]] = relationship(back_populates="star")
    galaxy: Mapped["Galaxy"] = relationship(back_populates="stars")
    galaxy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("galaxy.id"))


class StarCreate(BaseModel):
    name: str

    __relationships__ = ["planets", "galaxy"]


class StarRead(BaseModel):
    id: int
    name: str
    color: str
    brightness: int = 1

    __relationships__ = ["planets", "galaxy"]


class StarUpdate(BaseModel):
    name: Optional[str]

    __relationships__ = ["planets", "galaxy"]


class Cluster(Base):
    __tablename__ = "cluster"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str]


class Galaxy(Base):
    __tablename__ = "galaxy"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    stars: Mapped[list[Star]] = relationship(back_populates="galaxy")
    favorite_planets: Mapped[list[Planet]] = relationship(
        back_populates="favorite_galaxy"
    )

    cluster_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cluster.id"))
    cluster: Mapped[Optional[Cluster]] = relationship()


class GalaxyCreate(BaseModel):
    name: str

    __relationships__ = ["stars", "favorite_planets"]


class GalaxyRead(BaseModel):
    id: int
    name: str

    __relationships__ = ["stars", "favorite_planets"]


GalaxyCreate.model_rebuild()
StarRead.model_rebuild()
StarCreate.model_rebuild()
PlanetRead.model_rebuild()


class GalaxyUpdate(BaseModel):
    name: Optional[str] = None


class Moon(Base):
    __tablename__ = "moon"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    planet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("planet.id"))
    planet: Mapped[Planet] = relationship()


class MoonRead(BaseModel):
    id: int
    name: str

    __relationships__ = ["planet"]


class Asteroid(Base):
    __tablename__ = "asteroid"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class AsteroidRead(BaseModel):
    id: str = Field(alias="name")


class PlanetResource(SQLAlchemyResource):
    engine = engine
    name = "planet"
    Db = Planet
    Read = PlanetRead
    Create = PlanetCreate


class StarResource(SQLAlchemyResource[Star]):
    engine = engine
    name = "star"
    Db = Star
    Read = StarRead
    Create = StarCreate
    Update = StarUpdate
    Paginator = paginators.LimitOffsetPaginator

    def get_joins(self):
        request = self.context.get("request")
        if request and request.query_params.get("filter[galaxy.name]"):
            return [Star.galaxy]

        return super().get_joins()

    def get_where(self):
        request = self.context.get("request")

        if request and (galaxy_name := request.query_params.get("filter[galaxy.name]")):
            return [Galaxy.name == galaxy_name]

        return []


class GalaxyResource(SQLAlchemyResource[Galaxy]):
    engine = engine
    name = "galaxy"
    Db = Galaxy
    Read = GalaxyRead
    Create = GalaxyCreate
    Update = GalaxyUpdate


class MoonResource(SQLAlchemyResource[Moon]):
    engine = engine
    name = "moon"
    Db = Moon
    Read = MoonRead


class AsteroidResource(SQLAlchemyResource[Asteroid]):
    engine = engine
    name = "asteroid"
    Db = Asteroid
    Read = AsteroidRead
    id_field = "name"

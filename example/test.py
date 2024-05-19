from typing import List, Optional

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from fastapi_resources import resources, routers
from fastapi_resources.resources.sqlalchemy import paginators
from fastapi_resources.resources.sqlalchemy.resources import SQLAlchemyResource
from fastapi_resources.routers import decorators

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

app = FastAPI()


class Base(DeclarativeBase):
    pass


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(engine)


class Planet(Base):
    __tablename__ = "planet"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    star: Mapped["Star"] = relationship(back_populates="planets")
    favorite_galaxy: Mapped["Galaxy"] = relationship(back_populates="favorite_planets")
    star_id: Mapped[Optional[int]] = mapped_column(ForeignKey("star.id"))
    favorite_galaxy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("galaxy.id"))


class PlanetCreate(BaseModel):
    name: str
    star_id: Optional[int] = None
    favorite_galaxy_id: Optional[int] = None


class PlanetRead(BaseModel):
    id: str

    name: str
    star: Optional[BaseModel] = None
    favorite_galaxy: Optional[BaseModel] = None


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

    planets: Optional[BaseModel] = None
    galaxy: Optional[BaseModel] = None


class StarRead(BaseModel):
    id: int
    name: str
    color: str
    brightness: int = 1

    planets: Optional[BaseModel] = None
    galaxy: Optional[BaseModel] = None


class StarUpdate(BaseModel):
    name: Optional[str]

    planets: Optional[BaseModel] = None
    galaxy: Optional[BaseModel] = None


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

    stars: BaseModel
    favorite_planets: BaseModel


class GalaxyRead(BaseModel):
    id: int
    name: str

    stars: BaseModel
    favorite_planets: BaseModel


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

    planet: BaseModel


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


class GalaxyResourceRouter(routers.JSONAPIResourceRouter):
    resource_class = GalaxyResource

    @decorators.action(detail=False)
    def distant_galaxies(self, request: Request):
        resource = self.get_resource(request=request)
        return resource.list()

    @decorators.action(detail=True, methods=["patch"])
    def rename(self, id: int, request: Request):
        resource = self.get_resource(request=request)
        obj = resource.update(id=id, model=GalaxyUpdate(name="Andromeda"))
        return obj


galaxy = GalaxyResourceRouter(resource_class=GalaxyResource, tags=["Galaxies"])
star = routers.JSONAPIResourceRouter(resource_class=StarResource, tags=["Stars"])
planet = routers.JSONAPIResourceRouter(resource_class=PlanetResource, tags=["Planets"])

app.include_router(galaxy)
app.include_router(star)
app.include_router(planet)

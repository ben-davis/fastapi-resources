from typing import List, Optional

from fastapi import FastAPI, Request
from sqlmodel import Field, Relationship, SQLModel, create_engine

from fastapi_rest_framework import resources, routers
from fastapi_rest_framework.routers import decorators

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)

app = FastAPI()


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


class PlanetBase(SQLModel):
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


class PlanetUpdate(SQLModel):
    name: Optional[str] = None
    favorite_galaxy_id: Optional[str] = None


class StarBase(SQLModel):
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


class StarUpdate(SQLModel):
    name: Optional[str] = None


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


class PlanetResource(resources.SQLModelResource[Planet]):
    engine = engine
    name = "planet"
    Db = Planet
    Read = PlanetRead
    Create = PlanetCreate
    Update = PlanetUpdate


class StarResource(resources.SQLModelResource[Star]):
    engine = engine
    name = "star"
    Db = Star
    Read = StarRead
    Create = StarCreate
    Update = StarUpdate


class GalaxyResource(resources.SQLModelResource[Galaxy]):
    engine = engine
    name = "galaxy"
    Db = Galaxy
    Read = GalaxyRead
    Create = GalaxyCreate
    Update = GalaxyUpdate


class GalaxyResourceRouter(routers.ResourceRouter[GalaxyResource]):
    @decorators.action(detail=False)
    def distant_galaxies(self, request: Request):
        resource = self.get_resource(request=request)
        return resource.list()

    @decorators.action(detail=True, methods=["patch"])
    def rename(self, id: int, request: Request):
        resource = self.get_resource(request=request)
        obj = resource.update(id=id, model=GalaxyUpdate(name="Andromeda"))
        return obj


galaxy = GalaxyResourceRouter(
    prefix="/galaxies", resource_class=GalaxyResource, tags=["Galaxies"]
)
star = routers.JSONAPIResourceRouter(
    prefix="/stars", resource_class=StarResource, tags=["Stars"]
)
planet = routers.JSONAPIResourceRouter(
    prefix="/planets", resource_class=PlanetResource, tags=["Planets"]
)

app.include_router(galaxy)
app.include_router(star)
app.include_router(planet)


"""
TODO:
x Relationships and automatically supported and documented `includes` with efficient prefetches.
x Nested relationships
- Post create & update hooks.
    - Ensure it can support things like easily saving the user from the request as an attr on a model
x An equivalent of get_queryset so users can do row-level permissions.
- How to support actions?
x Can JSON:API be an optional thing?
- Filtering/sorting on lists
- All other JSON:API compliance
"""

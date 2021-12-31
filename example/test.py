from typing import List, Optional

from fastapi import FastAPI
from sqlmodel import Field, Relationship, SQLModel, create_engine

from fastapi_rest_framework import resources, routers

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)

app = FastAPI()


class PlanetBase(SQLModel):
    star: str
    location: str


class Planet(PlanetBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    teams: List["Team"] = Relationship(back_populates="planet")


class PlanetCreate(PlanetBase):
    pass


class PlanetRead(PlanetBase):
    id: str


class PlanetUpdate(SQLModel):
    id: Optional[str] = None
    star: Optional[str] = None
    location: Optional[str] = None


class TeamBase(SQLModel):
    name: str
    headquarters: str

    planet_id: Optional[int] = Field(default=None, foreign_key="planet.id")


class Team(TeamBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    heroes: List["Hero"] = Relationship(back_populates="team")
    planet: Optional[Planet] = Relationship(back_populates="teams")


class TeamCreate(TeamBase):
    pass


class TeamRead(TeamBase):
    id: str


class TeamUpdate(SQLModel):
    id: Optional[str] = None
    name: Optional[str] = None
    headquarters: Optional[str] = None


class HeroBase(SQLModel):
    name: str
    secret_name: str
    age: Optional[int] = None

    team_id: Optional[int] = Field(default=None, foreign_key="team.id")


class Hero(HeroBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    team: Optional[Team] = Relationship(back_populates="heroes")


class HeroCreate(HeroBase):
    pass


class HeroRead(HeroBase):
    id: str


class HeroUpdate(SQLModel):
    name: Optional[str] = None
    secret_name: Optional[str] = None
    age: Optional[int] = None
    team_id: Optional[int] = None


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


class TeamResource(resources.SQLModelResource):
    name = "team"
    engine = engine
    Db = Team
    Read = TeamRead
    Create = TeamCreate
    Update = TeamUpdate


class HeroResource(resources.SQLModelResource):
    name = "hero"
    engine = engine
    Db = Hero
    Read = HeroRead
    Create = HeroCreate
    Update = HeroUpdate


class PlanetResource(resources.SQLModelResource):
    name = "planet"
    engine = engine
    Db = Planet
    Read = PlanetRead
    Create = PlanetCreate
    Update = PlanetUpdate


team = routers.JSONAPIResourceRouter(
    prefix="/teams", resource_class=TeamResource, tags=["Teams"]
)
hero = routers.JSONAPIResourceRouter(
    prefix="/heroes", resource_class=HeroResource, tags=["Heroes"]
)
planet = routers.JSONAPIResourceRouter(
    prefix="/planets", resource_class=PlanetResource, tags=["Planets"]
)

app.include_router(hero)
app.include_router(team)
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

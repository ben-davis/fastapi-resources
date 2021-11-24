from typing import List, Optional

from fastapi import FastAPI, Request
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine

from fastapi_rest_framework import resources, routers

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)

app = FastAPI()


class TeamBase(SQLModel):
    name: str
    headquarters: str


class Team(TeamBase, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)

    heroes: List["Hero"] = Relationship(back_populates="team")


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


hero_resource = HeroResource()
team_resource = TeamResource()

team = routers.ResourceRouter(prefix="/teams", resource=team_resource, tags=["Teams"])
hero = routers.ResourceRouter(prefix="/heroes", resource=hero_resource, tags=["Heroes"])

app.include_router(hero)
app.include_router(team)


"""
TODO:
x Relationships and automatically supported and documented `includes` with efficient prefetches.
- Nested relationships
- Post create & update hooks.
x An equivalent of get_queryset so users can do row-level permissions.
- How to support actions?
- Can JSON:API be an optional thing?
"""

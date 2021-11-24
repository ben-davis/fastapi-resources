from typing import List, Optional

from fastapi import FastAPI
from sqlmodel import Field, Relationship, SQLModel, create_engine

import generics

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)

app = FastAPI()


class TeamBase(SQLModel):
    name: str
    headquarters: str


class Team(TeamBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    heroes: List["Hero"] = Relationship(back_populates="team")


class TeamCreate(TeamBase):
    pass


class TeamRead(TeamBase):
    id: int


class TeamUpdate(SQLModel):
    id: Optional[int] = None
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
    id: int


class HeroUpdate(SQLModel):
    name: Optional[str] = None
    secret_name: Optional[str] = None
    age: Optional[int] = None
    team_id: Optional[int] = None


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


class TeamResource(generics.FullResource):
    name = "team"
    engine = engine
    Db = Team
    Read = TeamRead
    Create = TeamCreate
    Update = TeamUpdate

class HeroResource(generics.FullResource):
    name = "hero"
    engine = engine
    Db = Hero
    Read = HeroRead
    Create = HeroCreate
    Update = HeroUpdate




hero_resource = HeroResource()
team_resource = TeamResource()

team = generics.ResourceRouter(prefix="/teams", resource=team_resource, tags=["Teams"])
hero = generics.ResourceRouter(
    prefix="/heroes", resource=hero_resource, tags=["Heroes"]
)

app.include_router(hero)
app.include_router(team)


"""
TODO:
- Relationships and automatically supported and documented `includes` with efficient prefetches.
- Post create & update hooks.
- An equivalent of get_queryset so users can do row-level permissions.
- How to support actions?
"""

from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from tests.routers import in_memory_resource


class PlanetBase(SQLModel):
    name: str

    star_id: Optional[int] = Field(default=None, foreign_key="star.id")


class Planet(PlanetBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    star: "Star" = Relationship(back_populates="planets")


class PlanetCreate(PlanetBase):
    pass


class PlanetRead(PlanetBase):
    id: int


class PlanetUpdate(SQLModel):
    id: Optional[int] = None
    name: Optional[str] = None


class StarBase(SQLModel):
    name: str


class Star(StarBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    planets: Planet = Relationship(back_populates="star")


class StarCreate(StarBase):
    pass


class StarRead(StarBase):
    id: int


class StarUpdate(SQLModel):
    id: Optional[int] = None
    name: Optional[str] = None


class PlanetResource(in_memory_resource.InMemorySQLModelResource):
    name = "planet"
    Db = Planet
    Read = PlanetRead
    Create = PlanetCreate
    Update = PlanetUpdate


class StarResource(in_memory_resource.InMemorySQLModelResource):
    name = "star"
    Db = Star
    Read = StarRead
    Create = StarCreate
    Update = StarUpdate

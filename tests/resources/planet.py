import uuid
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .sqlmodel_models import Galaxy, Star


class PlanetBase(SQLModel):
    name: str

    star_id: Optional[int] = Field(default=None, foreign_key="star.id")
    favorite_galaxy_id: Optional[int] = Field(default=None, foreign_key="galaxy.id")


class Planet(PlanetBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)

    star: "Star" = Relationship(back_populates="planets")
    favorite_galaxy: "Galaxy" = Relationship(back_populates="favorite_planets")


class PlanetCreate(PlanetBase):
    pass


class PlanetRead(PlanetBase):
    id: str

    star: "Star" = Relationship(back_populates="planets")
    favorite_galaxy: "Galaxy" = Relationship(back_populates="favorite_planets")

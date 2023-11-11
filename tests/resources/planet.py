import uuid
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tests.resources.sqlalchemy_base import Base

if TYPE_CHECKING:
    from .sqlalchemy_models import Galaxy, Star


class Planet(Base):
    __tablename__ = "planet"

    id: Mapped[str] = mapped_column(
        default_factory=lambda: str(uuid.uuid4()), primary_key=True
    )
    name: Mapped[str]

    star_id: Mapped[Optional[int]] = mapped_column(ForeignKey("star.id"), init=False)
    star: Mapped["Star"] = relationship(back_populates="planets")

    favorite_galaxy_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("galaxy.id"), init=False
    )
    favorite_galaxy: Mapped[Optional["Galaxy"]] = relationship(
        back_populates="favorite_planets", default=None
    )


class PlanetCreate(BaseModel):
    name: str


class PlanetRead(BaseModel):
    id: str
    name: str

    __relationships__ = ["star", "favorite_galaxy"]

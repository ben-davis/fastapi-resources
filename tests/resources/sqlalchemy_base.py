from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.decl_api import MappedAsDataclass


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    pass

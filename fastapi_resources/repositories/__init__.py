from typing import Any, Optional

from sqlalchemy import delete, func, inspect as sa_inspect, select
from sqlalchemy.orm import Session
from sqlalchemy import exc as sa_exceptions


class BaseSqlAlchemyRepo:
    """Base class for generated SQLAlchemy repositories.

    Subclass to override get_where() or get_joins() for row-level filtering.
    """

    Db: type  # set by build_sqlalchemy_repo

    def __init__(self, session: Session, context: Optional[dict] = None, id_field: Optional[str] = None):
        self.session = session
        self.context = context or {}
        self._id_field_name = id_field  # overrides PK lookup when set

    def add(self, obj) -> None:
        self.session.add(obj)
        self.session.flush()  # assigns autoincrement PKs immediately

    def remove(self, obj) -> None:
        self.session.delete(obj)

    def get(self, id, method: str = "retrieve", options: Optional[list] = None) -> Any:
        from fastapi_resources.resources.sqlalchemy.exceptions import NotFound

        stmt = self.get_select(method=method).where(self._id_field() == id)
        if options:
            stmt = stmt.options(*options)
        try:
            return self.session.scalars(stmt).unique().one()
        except sa_exceptions.NoResultFound:
            raise NotFound(f"{self.Db.__name__.lower()} not found")

    def delete_all(self) -> None:
        where = self.get_where(method="delete_all")
        self.session.execute(delete(self.Db).where(*where))
        self.session.commit()

    def list(
        self,
        options: Optional[list] = None,
        paginator=None,
        method: str = "list",
    ) -> tuple[list, Optional[str], int]:
        stmt = self.get_select(method=method)

        if options:
            stmt = stmt.options(*options)

        if paginator:
            stmt = paginator.paginate_select(stmt)

        rows = self.session.scalars(stmt).unique().all()
        count = self.session.scalars(self.get_count_select(method=method)).one()
        next_cursor = paginator.get_next(count=count) if paginator else None

        return rows, next_cursor, count

    def get_where(self, method: str) -> list:
        return []

    def get_joins(self) -> list:
        return []

    def get_select(self, method: str):
        stmt = select(self.Db)

        for join in self.get_joins():
            stmt = stmt.join(join)

        if where := self.get_where(method=method):
            stmt = stmt.where(*where)

        return stmt

    def get_count_select(self, method: str):
        stmt = select(func.count(self._id_field()))

        for join in self.get_joins():
            stmt = stmt.join(join)

        if where := self.get_where(method=method):
            stmt = stmt.where(*where)

        return stmt

    def _id_field(self):
        if self._id_field_name:
            return getattr(self.Db, self._id_field_name)
        inspected = sa_inspect(self.Db)
        pk_name = inspected.mapper.primary_key[0].key
        return getattr(self.Db, pk_name)


def build_sqlalchemy_repo(Db: type) -> type:
    """Generate a SQLAlchemy repository class for the given ORM model."""
    return type(
        f"{Db.__name__}Repo",
        (BaseSqlAlchemyRepo,),
        {"Db": Db},
    )

from typing import Optional

from sqlmodel.sql.expression import SelectOfScalar


class LimitOffsetPaginator:
    def __init__(self, cursor: Optional[str] = None, limit: Optional[int] = None):
        self.page = int(cursor) if cursor else 1
        self.limit = limit or 20

    def paginate_select(self, select: SelectOfScalar):
        return select.limit(self.limit).offset((self.page - 1) * self.limit)

    def get_next(self, count: int):
        current_max = self.page * self.limit

        if count > current_max:
            return str(self.page + 1)

        return None

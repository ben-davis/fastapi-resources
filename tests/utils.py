import contextlib

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.base import Connection


@contextlib.contextmanager
def assert_num_queries(engine: Engine, num: int):
    statements = []

    def callback(conn: Connection, cursor: int, statement: str, *args, **kwargs):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", callback)

    try:
        yield
    finally:
        event.remove(engine, "before_cursor_execute", callback)

        new_line = "\n\n"

        assert (
            len(statements) == num
        ), f"Expected {num} queries, found {len(statements)}: {new_line}{new_line.join(statements)}"

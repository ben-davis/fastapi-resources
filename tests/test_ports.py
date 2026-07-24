"""The concrete implementations must satisfy the Repository / UnitOfWork ports."""
from sqlalchemy.orm import sessionmaker

from fastapi_resources import (
    Repository,
    SqlAlchemyUnitOfWork,
    UnitOfWork,
    build_sqlalchemy_repo,
)
from tests.resources.sqlalchemy_models import Galaxy, engine


def test_sqlalchemy_repo_satisfies_repository_port():
    repo = build_sqlalchemy_repo(Galaxy)(session=None)
    assert isinstance(repo, Repository)


def test_sqlalchemy_uow_satisfies_unit_of_work_port():
    uow = SqlAlchemyUnitOfWork(sessionmaker(engine))
    assert isinstance(uow, UnitOfWork)

import os

import pytest

from manygit.gitlab import GitLabPersonalAccessTokenAuth
from manygit.types import ConnectionManager, Repository


@pytest.fixture
def main_commit() -> str:
    return "b0a6a46bcd70bf305d59ea86431affc1db6c27ac"


@pytest.fixture
def branch_commit() -> str:
    return "41d680e26e1a9dbe662c936716076cee72941215"


@pytest.fixture
def personal_access_token() -> str:
    return os.environ["GITLAB_ACCESS_TOKEN"]


@pytest.fixture
def conn(personal_access_token: str) -> ConnectionManager:
    cm = ConnectionManager()
    cm.add_connection(
        GitLabPersonalAccessTokenAuth(
            personal_access_token=personal_access_token,
        )
    )

    return cm


@pytest.fixture
def repo(conn: ConnectionManager) -> Repository:
    return conn.get_repo("https://gitlab.com/davidmreed/manygit-test")


from .shared import *  # noqa

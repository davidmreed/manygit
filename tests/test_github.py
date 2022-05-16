import os

import pytest

from manygit.github import GitHubPersonalAccessTokenAuth
from manygit.types import ConnectionManager, Repository


@pytest.fixture
def main_commit() -> str:
    return "0ab718932f224846be22c284cd4fd8f667b35c7b"


@pytest.fixture
def branch_commit() -> str:
    return "fa01244214a7e645a837ade228eaff17df6d7e62"


@pytest.fixture
def personal_access_token() -> str:
    return os.environ["GITHUB_ACCESS_TOKEN"]


@pytest.fixture
def conn(personal_access_token: str) -> ConnectionManager:
    cm = ConnectionManager()
    cm.add_connection(
        GitHubPersonalAccessTokenAuth(
            username="davidmreed",
            personal_access_token=personal_access_token,
        )
    )

    return cm


@pytest.fixture
def repo(conn: ConnectionManager) -> Repository:
    return conn.get_repo("https://github.com/davidmreed/manygit-test")


from .shared import *  # noqa

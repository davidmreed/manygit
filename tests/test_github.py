import os

import pytest

from manygit.github import GitHubPersonalAccessTokenAuth
from manygit.types import CommitStatusEnum, ConnectionManager, Repository

main_commit = "0ab718932f224846be22c284cd4fd8f667b35c7b"

branch_commit = "fa01244214a7e645a837ade228eaff17df6d7e62"


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


def test_branches(repo: Repository):
    assert set(branch.name for branch in repo.branches) == set(
        ["main", "feature/add-file"]
    )

    branch = repo.get_branch("feature/add-file")
    assert branch
    assert branch.head.sha == branch_commit
    assert repo.default_branch.name == "main"


def test_commits(repo: Repository):
    commit = repo.get_commit(branch_commit)
    assert commit.sha == branch_commit
    assert list(parent.sha for parent in commit.parents) == [main_commit]


def test_commit_statuses(repo: Repository):
    commit = repo.get_commit(main_commit)
    assert set(status.name for status in commit.statuses) == set(["foo", "bar"])

    for cs in commit.statuses:
        if cs.name == "foo":
            assert cs.name == "foo"
            assert cs.status is CommitStatusEnum.SUCCESS
            assert cs.data is None
            assert cs.url is None
        else:
            assert cs.name == "bar"
            assert cs.status is CommitStatusEnum.FAILED
            assert cs.data is None
            assert cs.url == "https://ktema.org"


def test_tags(repo: Repository):
    assert len(list(repo.tags)) == 1
    tag = repo.get_tag("test")
    assert tag
    assert tag.commit.sha == main_commit
    assert tag.name == "test"
    assert tag.annotation.strip() == "This is the tag message."


def test_releases(repo: Repository):
    assert len(list(repo.releases)) == 1
    release = next(repo.releases)
    assert release
    assert release.tag.name == "test"
    assert release.name == "test"
    assert release.body.strip() == "Here are the release notes."
    assert release.commit.sha == main_commit


def test_pull_requests(repo: Repository):
    assert len(list(repo.pull_requests)) == 1
    pull_request = next(repo.pull_requests)
    assert pull_request
    assert pull_request.base.name == "main"
    assert pull_request.source.name == "feature/add-file"

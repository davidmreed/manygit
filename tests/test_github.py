import os

import pytest

from manygit import CommitStatusEnum, ConnectionManager, Repository
from manygit.exceptions import ManygitException
from manygit.github import (
    GitHubConnection,
    GitHubPersonalAccessTokenAuth,
    GitHubRepository,
    commit_status_from_github_status,
    commit_status_to_github_status,
)


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
def username() -> str:
    return os.environ["GITHUB_USERNAME"]


@pytest.fixture
def conn(personal_access_token: str, username: str) -> ConnectionManager:
    cm = ConnectionManager()
    cm.add_connection(
        GitHubPersonalAccessTokenAuth(
            username=username,
            personal_access_token=personal_access_token,
        )
    )

    return cm


@pytest.fixture
def fake_conn() -> GitHubConnection:
    return GitHubConnection(
        GitHubPersonalAccessTokenAuth(personal_access_token="foo", username="bar")
    )


@pytest.fixture
def fake_enterprise_conn() -> GitHubConnection:
    return GitHubConnection(
        GitHubPersonalAccessTokenAuth(
            personal_access_token="foo",
            username="bar",
            enterprise_url="https://github.ravenwood.com/",
        )
    )


@pytest.fixture
def repo(conn: ConnectionManager) -> Repository:
    return conn.get_repo("https://github.com/davidmreed/manygit-test")


from .shared import *  # noqa

# TODO: expand abstracted functionality to cover the setup and cleanup needs of integration tests.


@pytest.fixture
def test_branches(repo, branch_commit, main_commit):
    repo.repo.create_branch_ref("foo", main_commit)
    repo.repo.create_branch_ref("bar", branch_commit)

    yield (repo.get_branch("foo"), repo.get_branch("bar"))

    assert (
        repo.repo._delete(
            "https://api.github.com/repos/davidmreed/manygit-test/git/refs/heads/foo"
        ).status_code
        == 204
    )
    assert (
        repo.repo._delete(
            "https://api.github.com/repos/davidmreed/manygit-test/git/refs/heads/bar"
        ).status_code
        == 204
    )


@pytest.mark.vcr
def test_merge_branches(repo, main_commit, branch_commit, test_branches):
    # Create two branches and merge them together
    (foo, bar) = test_branches

    assert repo.merge_branches(foo, bar)
    commit_parents = list(repo.get_branch(foo.name).head.parents)
    assert set([commit.sha for commit in commit_parents]) == set(
        [main_commit, branch_commit]
    )


@pytest.mark.vcr
def test_create_tag(repo):
    t = repo.create_tag("foo", repo.default_branch.head, "This is a test tag")

    try:
        assert t.name == "foo"
        assert t.commit.sha == repo.default_branch.head.sha
        assert t.annotation == "This is a test tag"
    finally:
        t.tag._delete(
            "https://api.github.com/repos/davidmreed/manygit-test/git/refs/tags/foo"
        )


@pytest.mark.vcr
def test_create_release(repo):
    t = repo.create_tag("foo", repo.default_branch.head, "This is a test tag")
    r = repo.create_release(
        t, "Foo Release", "These are some release notes", True, False
    )

    try:
        assert r.name == "Foo Release"
        assert r.body.strip() == "These are some release notes"
        assert r.tag.name == "foo"
        assert r.is_prerelease
        assert not r.is_draft
    finally:
        assert r.release.delete()
        assert (
            t.tag._delete(
                "https://api.github.com/repos/davidmreed/manygit-test/git/refs/tags/foo"
            ).status_code
            == 204
        )


@pytest.mark.vcr
def test_pull_request(repo, test_branches, main_commit, branch_commit):
    foo, bar = test_branches

    pr = repo.create_pull_request("Test PR", foo, bar, "This is the body")
    assert pr.base.name == foo.name
    assert pr.source.name == bar.name

    pr.merge()

    commit_parents = list(repo.get_branch(foo.name).head.parents)
    assert set([commit.sha for commit in commit_parents]) == set(
        [main_commit, branch_commit]
    )


@pytest.mark.vcr
def test_set_commit_status(repo: GitHubRepository, test_branches):
    foo, _ = test_branches
    # GitHub doesn't allow us to delete a commit status.
    # We'll create a temporary branch and commit to apply it.
    content = repo.repo.file_contents("/README.md")
    assert content
    commit = repo.get_commit(
        content.update(
            "commit message", "file content".encode("utf-8"), branch=foo.name
        )["commit"].sha
    )

    commit.set_commit_status(
        CommitStatusEnum.SUCCESS,
        "Manygit Test",
        "Description",
        "https://github.com/davidmreed/manygit",
    )

    statuses = list(commit.statuses)
    assert len(statuses) == 1
    assert statuses[0].status is CommitStatusEnum.SUCCESS
    assert statuses[0].name == "Manygit Test"


def test_is_eligible_repo(fake_conn: GitHubConnection):
    assert fake_conn.is_eligible_repo("https://github.com/davidmreed/manygit") == (
        True,
        "davidmreed/manygit",
    )
    assert fake_conn.is_eligible_repo("git@github.com:davidmreed/manygit") == (
        True,
        "davidmreed/manygit",
    )
    assert fake_conn.is_eligible_repo("ssh://git@github.com:davidmreed/manygit") == (
        True,
        "davidmreed/manygit",
    )
    assert fake_conn.is_eligible_repo("git@github.com:davidmreed/manygit.git") == (
        True,
        "davidmreed/manygit",
    )
    assert fake_conn.is_eligible_repo("davidmreed/manygit") == (
        True,
        "davidmreed/manygit",
    )

    assert fake_conn.is_eligible_repo("git@gitlab.com:davidmreed/manygit.git") == (
        False,
        None,
    )


def test_is_eligible_repo__enterprise(fake_enterprise_conn: GitHubConnection):
    assert fake_enterprise_conn.is_eligible_repo(
        "https://github.ravenwood.com/davidmreed/manygit"
    ) == (True, "davidmreed/manygit")
    assert fake_enterprise_conn.is_eligible_repo(
        "git@github.ravenwood.com:davidmreed/manygit"
    ) == (True, "davidmreed/manygit")
    assert fake_enterprise_conn.is_eligible_repo(
        "ssh://git@github.ravenwood.com:davidmreed/manygit"
    ) == (True, "davidmreed/manygit")
    assert fake_enterprise_conn.is_eligible_repo(
        "git@github.ravenwood.com:davidmreed/manygit.git"
    ) == (True, "davidmreed/manygit")


def test_commit_status_to_github():
    assert commit_status_from_github_status("pending") is CommitStatusEnum.PENDING
    assert commit_status_from_github_status("error") is CommitStatusEnum.FAILED
    assert commit_status_from_github_status("failure") is CommitStatusEnum.FAILED
    assert commit_status_from_github_status("success") is CommitStatusEnum.SUCCESS

    with pytest.raises(ManygitException):
        commit_status_from_github_status("foo")


def test_commit_status_from_github():
    assert commit_status_to_github_status(CommitStatusEnum.PENDING) == "pending"
    assert commit_status_to_github_status(CommitStatusEnum.FAILED) == "failure"
    assert commit_status_to_github_status(CommitStatusEnum.SUCCESS) == "success"

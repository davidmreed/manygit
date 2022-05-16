import os
import time
import typing as T

import pytest
from gitlab.v4.objects import ProjectCommit

from manygit.exceptions import UnsupportedException
from manygit.gitlab import GitLabCommit, GitLabPersonalAccessTokenAuth, GitLabRepository
from manygit.types import CommitStatusEnum, ConnectionManager, Repository


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


@pytest.fixture
def test_branches(repo, branch_commit, main_commit):
    foo = repo.repo.branches.create({"branch": "foo", "ref": main_commit})
    bar = repo.repo.branches.create({"branch": "bar", "ref": branch_commit})

    yield (repo.get_branch("foo"), repo.get_branch("bar"))

    foo.delete()
    bar.delete()


def test_merge_branches(repo, main_commit, branch_commit, test_branches):
    # Create two branches and merge them together
    (foo, bar) = test_branches

    with pytest.raises(UnsupportedException):
        repo.merge_branches(foo, bar)


def test_create_tag(repo):
    t = repo.create_tag("foo", repo.default_branch.head, "This is a test tag")

    try:
        assert t.name == "foo"
        assert t.commit.sha == repo.default_branch.head.sha
        assert t.annotation == "This is a test tag"
    finally:
        t.tag.delete()


def test_create_release(repo: GitLabRepository):
    t = repo.create_tag("foo", repo.default_branch.head, "This is a test tag")
    r = repo.create_release(
        t, "Foo Release", "These are some release notes", True, False
    )

    try:
        assert r.name == "Foo Release"
        assert r.body.strip() == "These are some release notes"
        assert r.tag.name == "foo"
    finally:
        r.release.manager.delete(r.release.get_id())  # type: ignore
        t.tag.delete()


def test_create_pull_request(
    repo: GitLabRepository, test_branches, main_commit, branch_commit
):
    foo, bar = test_branches

    pr = repo.create_pull_request("Test PR", foo, bar, "This is the body")
    assert pr.base.name == foo.name
    assert pr.source.name == bar.name

    # GitLab appears to require a slight wait before merging a freshly-created PR.
    # Otherwise, it returns HTTP 406 branch cannot be merged.
    time.sleep(10)
    pr.merge()

    commit_parents = list(repo.get_branch(foo.name).head.parents)
    assert set([commit.sha for commit in commit_parents]) == set(
        [main_commit, branch_commit]
    )


def test_set_commit_status(repo: GitLabRepository, test_branches):
    foo, _ = test_branches
    # Create a temporary branch and commit to apply the status to.
    commit = GitLabCommit(
        T.cast(
            ProjectCommit,
            repo.repo.commits.create(
                {
                    "branch": foo.name,
                    "commit_message": "manygit test",
                    "actions": [
                        {
                            "action": "create",
                            "file_path": "foo.txt",
                            "content": "testing",
                        }
                    ],
                }
            ),
        )
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

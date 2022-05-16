from manygit.types import CommitStatusEnum, Repository


def test_branches(repo: Repository, branch_commit: str):
    assert set(branch.name for branch in repo.branches) == set(
        ["main", "feature/add-file"]
    )

    branch = repo.get_branch("feature/add-file")
    assert branch
    assert branch.head.sha == branch_commit
    assert repo.default_branch.name == "main"


def test_commits(repo: Repository, branch_commit: str, main_commit: str):
    commit = repo.get_commit(branch_commit)
    assert commit.sha == branch_commit
    assert list(parent.sha for parent in commit.parents) == [main_commit]


def test_commit_statuses(repo: Repository, main_commit: str):
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


def test_tags(repo: Repository, main_commit: str):
    assert len(list(repo.tags)) == 1
    tag = repo.get_tag("test")
    assert tag
    assert tag.commit.sha == main_commit
    assert tag.name == "test"
    assert tag.annotation.strip() == "This is the tag message."


def test_releases(repo: Repository, main_commit: str):
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

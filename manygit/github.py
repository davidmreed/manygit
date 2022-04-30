import github3

from .types import (
    Connection,
    Branch,
    Commit,
    Tag,
    Release,
    CommitStatus,
    Commit,
    Repository,
    GitHubOAuthTokenAuth,
    GitHubPersonalAccessTokenAuth,
)
import typing as T

GitHubAuth = T.Union[GitHubOAuthTokenAuth, GitHubPersonalAccessTokenAuth]


class GitHubCommitStatus(CommitStatus):
    __slots__ = ["commit_status"]

    status: github3.repos.status.Status

    def __init__(self, commit_status: github3.repos.status.Status):
        self.commit_status = commit_status

    @property
    def name(self) -> str:
        return self.commit_status.context

    @property
    def status(self) -> str:
        return self.commit_status.state

    @property
    def data(self) -> str:
        return self.commit_status.description


GitHub3Commit = T.Union[
    github3.repos.commit.ShortCommit, github3.repos.commit.RepoCommit
]


class GitHubCommit(Commit):
    __slots__ = ["commit"]

    commit: GitHub3Commit

    def __init__(self, commit: GitHub3Commit):
        self.commit = commit

    @property
    def sha(self) -> str:
        return self.commit.sha

    @property
    def statuses(self) -> T.Iterable[CommitStatus]:
        for s in self.commit.statuses():
            yield GitHubCommitStatus(s)

    def download(self):
        raise NotImplementedError

    @property
    def parents(self) -> T.Iterable[Commit]:
        return [GitHubCommit(c) for c in self.commit.parents]


class GitHubBranch(Branch):
    __slots__ = ["branch"]

    branch: github3.repos.branch.ShortBranch

    def __init__(self, branch: github3.repos.branch.ShortBranch):
        self.branch = branch

    @property
    def name(self) -> str:
        return self.branch.name

    @property
    def head(self) -> Commit:
        # `self.branch.commit` is a MiniCommit, which we refresh
        # into a RepoCommit.
        return GitHubCommit(self.branch.commit.refresh())


class GitHubTag(Tag):
    __slots__ = ["tag"]

    tag: github3.repos.tag.RepoTag

    def __init__(self, tag: github3.repos.tag.RepoTag):
        self.tag = tag

    @property
    def name(self) -> str:
        return self.tag.name

    @property
    def commit(self) -> GitHubCommit:
        return GitHubCommit(self.tag.commit.refresh())

    @property
    def annotation(self) -> str:
        return self.tag.message


class GitHubRelease(Release):
    __slots__ = ["release"]

    release: github3.repos.release.Release

    def __init__(self, release: github3.repos.release.Release):
        self.release = release

    @property
    def tag(self) -> GitHubTag:
        return get_tag(self.release.tag_name)

    @property
    def name(self) -> str:
        return self.release.name

    @property
    def is_draft(self) -> bool:
        return self.release.draft

    @property
    def is_prerelease(self) -> bool:
        return self.release.prerelease


class GitHubRepository(Repository):
    __slots__ = ["repo"]

    def __init__(self, repo: github3.repos.repo.Repository):
        self.repo = repo

    def branches(self) -> T.Iterable[Branch]:
        for branch in self.repo.branches():
            yield self.get_branch(branch.name)

    def get_branch(self, name: str) -> Branch:
        return GitHubBranch(self.repo.branch(name))

    def tags(self) -> T.Iterable[Tag]:
        for t in self.repo.tags():
            yield GitHubTag(self.repo.get_tag(t))

    def get_tag(self, name: str) -> Tag:
        # TODO: how to get by name?
        return GitHubTag(self.repo.tag(sha))

    def get_releases(self) -> T.Iterable[Release]:
        for r in self.repo.get_releases():
            yield GitHubRelease(r)  # ?

    def get_release(self, tag_name: str) -> Release:
        # TODO: github3 returns None for not found
        return GitHubRelease(self.repo.release_from_tag(tag_name))

    def get_commit(self, sha: str) -> Commit:
        return GitHubCommit(self.repo.commit(sha))

    @property
    def default_branch(self) -> Branch:
        return self.get_branch(self.repo.default_branch)


class GitHubConnection(Connection):

    conn: T.Union[github3.github.GitHubEnterprise, github3.github.GitHub]
    enterprise_url: T.Optional[str]

    def __init__(
        self, auth: T.Union[GitHubOAuthTokenAuth, GitHubPersonalAccessTokenAuth]
    ):
        if isinstance(auth, GitHubPersonalAccessTokenAuth):
            args = {"username": auth.username, "password": auth.personal_access_token}
        else:
            args = {"token": auth.oauth_token}

        if auth.enterprise_url:
            self.conn = github3.github.GitHubEnterprise(auth.enterprise_url, **args)
            self.enterprise_url = auth.enterprise_url
        else:
            self.conn = github3.github.GitHub(**args)
            self.enterprise_url = None

    def get_repo(self, repo: str) -> GitHubRepository:
        return GitHubRepository(self.conn.repository(*repo.split("/")))

    def is_eligible_repo(self, repo: str) -> T.Tuple[bool, str]:
        # GitHub URL patterns
        # GitHub Enterprise URLs are the same, but replace `github.com` with the enterprise URL
        # https://github.com/davidmreed/amaxa.git
        # https://github.com/davidmreed/amaxa
        # git@github.com:davidmreed/amaxa.git
        # davidmreed/amaxa

        repo = repo.removeprefix("https://")
        repo = repo.removeprefix("ssh://")
        repo = repo.removesuffix(".git")

        # TODO: need to normalize enterprise_url to remove scheme
        if self.enterprise_url:
            enterprise_ssh_prefix = f"git@{self.enterprise_url}:"
            if repo.startswith(enterprise_ssh_prefix):
                return True, repo.removeprefix(enterprise_ssh_prefix)

            # TODO: trailing slashes
            if repo.startswith(self.enterprise_url):
                return True, repo.removeprefix(self.enterprise_url)

        if repo.startswith("git@github.com:"):
            return True, repo.removeprefix("git@github.com:")

        if repo.startswith("github.com/"):
            return True, repo.removeprefix("github.com/")

        splits = repo.split("/")
        if len(splits) == 2:
            return True, repo

        return False, None

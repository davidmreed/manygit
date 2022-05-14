import http
import typing as T
from dataclasses import dataclass

import github3
from github3.exceptions import GitHubException, TransportError

from .exceptions import ManygitException, NetworkError, VCSException, map_exceptions
from .types import (
    Branch,
    Commit,
    CommitStatus,
    CommitStatusData,
    CommitStatusEnum,
    Connection,
    PullRequest,
    PullRequestData,
    Release,
    ReleaseData,
    Repository,
    Tag,
    TagData,
    connection,
)

GITHUB_HOST = "GITHUB"


@dataclass
class GitHubOAuthTokenAuth:
    oauth_token: str
    enterprise_url: T.Optional[str] = None


@dataclass
class GitHubPersonalAccessTokenAuth:
    username: str
    personal_access_token: str
    enterprise_url: T.Optional[str] = None


GitHubAuth = T.Union[GitHubOAuthTokenAuth, GitHubPersonalAccessTokenAuth]

exc = map_exceptions({TransportError: NetworkError, GitHubException: VCSException})


class GitHubCommitStatus(CommitStatus):
    __slots__ = ["commit_status"]

    commit_status: github3.repos.status.Status

    def __init__(self, commit_status: github3.repos.status.Status):
        self.commit_status = commit_status

    @property
    def name(self) -> str:
        return self.commit_status.context

    @property
    def status(self) -> CommitStatusEnum:
        return GitHubCommitStatus.from_github_status(self.commit_status.state)

    @property
    def data(self) -> str:
        return self.commit_status.description

    @property
    def url(self) -> T.Optional[str]:
        return self.commit_status.target_url

    @staticmethod
    def from_github_status(status: str) -> CommitStatusEnum:
        if status == "pending":
            return CommitStatusEnum.PENDING
        elif status in ["failure", "error"]:
            return CommitStatusEnum.FAILED
        elif status == "success":
            return CommitStatusEnum.SUCCESS

        raise ManygitException(f"Invalid commit status value {str}")


def to_github_status(status: CommitStatusEnum) -> str:
    if status == CommitStatusEnum.PENDING:
        return "pending"
    elif status == CommitStatusEnum.FAILED:
        return "failure"

    return "success"


GitHub3Commit = T.Union[
    github3.repos.commit.ShortCommit, github3.repos.commit.RepoCommit
]


class GitHubCommit(Commit):
    __slots__ = ["commit"]

    commit: GitHub3Commit
    repo: "GitHubRepository"

    def __init__(self, commit: GitHub3Commit, repo: "GitHubRepository"):
        self.commit = commit
        self.repo = repo

    @property
    def sha(self) -> str:
        return self.commit.sha

    @property
    @exc
    def statuses(self) -> T.Iterable[CommitStatus]:
        for s in self.commit.statuses():
            yield GitHubCommitStatus(s)

    def download(self):
        raise NotImplementedError

    @property
    @exc
    def parents(self) -> T.Iterable[Commit]:
        return [self.repo.get_commit(c["sha"]) for c in self.commit.parents]


class GitHubBranch(Branch):
    __slots__ = ["branch", "repo"]

    branch: github3.repos.branch.ShortBranch
    repo: "GitHubRepository"

    def __init__(
        self, branch: github3.repos.branch.ShortBranch, repo: "GitHubRepository"
    ):
        self.branch = branch
        self.repo = repo

    @property
    def name(self) -> str:
        return self.branch.name

    @property
    @exc
    def head(self) -> Commit:
        # `self.branch.commit` is a MiniCommit, which we refresh
        # into a RepoCommit.
        return GitHubCommit(self.branch.commit.refresh(), self.repo)


class GitHubTag(Tag):
    __slots__ = ["tag"]

    tag: github3.repos.tag.RepoTag
    repo: "GitHubRepository"

    def __init__(self, tag: github3.repos.tag.RepoTag, repo: "GitHubRepository"):
        self.tag = tag
        self.repo = repo

    @property
    def name(self) -> str:
        return self.tag.tag

    @property
    def commit(self) -> GitHubCommit:
        return self.repo.get_commit(self.tag.object.sha)

    @property
    def annotation(self) -> str:
        return self.tag.message


class GitHubRelease(Release):
    __slots__ = ["release"]

    release: github3.repos.release.Release
    repo: "GitHubRepository"

    def __init__(
        self, release: github3.repos.release.Release, repo: "GitHubRepository"
    ):
        self.release = release
        self.repo = repo

    @property
    def tag(self) -> GitHubTag:
        return self.repo.get_tag(self.release.tag_name)

    @property
    def name(self) -> str:
        return self.release.name

    @property
    def body(self) -> str:
        return self.release.body

    @property
    def commit(self) -> Commit:
        return self.tag.commit

    @property
    def is_draft(self) -> bool:
        return self.release.draft

    @property
    def is_prerelease(self) -> bool:
        return self.release.prerelease


class GitHubPullRequest(PullRequest):

    pull_request: github3.pulls.ShortPullRequest
    repo: "GitHubRepository"

    def __init__(
        self, pull_request: github3.pulls.ShortPullRequest, repo: "GitHubRepository"
    ):
        self.pull_request = pull_request
        self.repo = repo

    @property
    def base(self) -> Branch:
        return self.repo.get_branch(self.pull_request.base.ref)

    @property
    def source(self) -> Branch:
        return self.repo.get_branch(self.pull_request.head.ref)


class GitHubRepository(Repository):
    __slots__ = ["repo"]

    repo: github3.repos.repo.Repository

    def __init__(self, repo: github3.repos.repo.Repository):
        self.repo = repo

    @property
    def commits(self) -> T.Iterable[GitHubCommit]:
        raise NotImplementedError

    @exc
    def get_commit(self, sha: str) -> GitHubCommit:
        return GitHubCommit(self.repo.commit(sha), self)

    @property
    @exc
    def branches(self) -> T.Iterable[GitHubBranch]:
        for branch in self.repo.branches():
            yield self.get_branch(branch.name)

    @exc
    def get_branch(self, name: str) -> GitHubBranch:
        return GitHubBranch(self.repo.branch(name), self)

    @property
    @exc
    def default_branch(self) -> GitHubBranch:
        return self.get_branch(self.repo.default_branch)

    @property
    @exc
    def tags(self) -> T.Iterable[GitHubTag]:
        for t in self.repo.tags():
            yield GitHubTag(t, self)

    @exc
    def get_tag(self, name: str) -> GitHubTag:
        return GitHubTag(self.repo.tag(self.repo.ref(f"tags/{name}").object.sha), self)

    @property
    @exc
    def releases(self) -> T.Iterable[GitHubRelease]:
        for r in self.repo.releases():
            yield GitHubRelease(r, self)

    @exc
    def get_release(self, tag_name: str) -> GitHubRelease:
        # TODO: github3 returns None for not found
        return GitHubRelease(self.repo.release_from_tag(tag_name), self)

    @property
    @exc
    def pull_requests(self) -> T.Iterable[GitHubPullRequest]:
        for pr in self.repo.pull_requests():
            yield GitHubPullRequest(pr, self)

    @exc
    def merge_branches(self, base: GitHubBranch, source: GitHubBranch) -> bool:
        if base.repo != self or source.repo != self:
            raise ManygitException("Branches must be associated with the same repo")

        try:
            self.repo.merge(base.name, source.head.sha)
        except github3.exceptions.GitHubError as e:
            if e.code != http.client.CONFLICT:
                raise

            return False

        return True

    @exc
    def set_commit_status(
        self, commit: GitHubCommit, commit_status: CommitStatusData
    ) -> GitHubCommitStatus:
        status = self.repo.create_status(
            sha=commit_status.commit.sha,
            state=to_github_status(commit_status.state),
            target_url=commit_status.url,
            description=commit_status.description,
            context=commit_status.name,
        )
        return GitHubCommitStatus(status)

    @exc
    def create_tag(self, data: TagData) -> GitHubTag:
        t = self.repo.create_tag(
            tag=data.tag_name,
            message=data.message,
            src=data.commit.sha,
            obj_type="commit",
        )
        return GitHubTag(t, self)

    @exc
    def create_release(self, data: ReleaseData) -> GitHubRelease:
        release = self.repo.create_release(
            tag_name=data.tag.name,
            name=data.name,
            body=data.body,
            prerelease=data.is_prerelease,
            draft=data.is_draft,
        )
        return GitHubRelease(release, self)

    @exc
    def create_pull_request(self, data: PullRequestData) -> GitHubPullRequest:
        pr = self.repo.create_pull(
            title=data.title, base=data.base.name, head=data.source.name, body=data.body
        )
        # raises UnprocessableEntity 422
        return GitHubPullRequest(pr, self)

    @exc
    def merge_pull_request(self, pull_request: GitHubPullRequest):
        ...


@connection(
    host=GITHUB_HOST, auth_classes=[GitHubOAuthTokenAuth, GitHubPersonalAccessTokenAuth]
)
class GitHubConnection(Connection):
    __slots__ = []

    conn: T.Union[github3.github.GitHubEnterprise, github3.github.GitHub]
    enterprise_url: T.Optional[str] = None

    @exc
    def __init__(
        self, auth: T.Union[GitHubOAuthTokenAuth, GitHubPersonalAccessTokenAuth]
    ):
        if isinstance(auth, GitHubPersonalAccessTokenAuth):
            args = {"username": auth.username, "password": auth.personal_access_token}
        else:
            args = {"token": auth.oauth_token}

        if auth.enterprise_url:
            self.conn = github3.github.GitHubEnterprise(auth.enterprise_url, **args)
            self.enterprise_url = auth.enterprise_url.removeprefix(
                "https://"
            ).removesuffix("/")
        else:
            self.conn = github3.github.GitHub(**args)
            self.enterprise_url = None

    @exc
    def get_repo(self, repo: str) -> GitHubRepository:
        return GitHubRepository(self.conn.repository(*repo.split("/")))

    def is_eligible_repo(self, repo: str) -> T.Tuple[bool, T.Optional[str]]:
        # GitHub URL patterns
        # GitHub Enterprise URLs are the same, but replace `github.com` with the enterprise URL
        # https://github.com/davidmreed/amaxa.git
        # https://github.com/davidmreed/amaxa
        # git@github.com:davidmreed/amaxa.git
        # davidmreed/amaxa

        repo = repo.removeprefix("https://")
        repo = repo.removeprefix("ssh://")
        repo = repo.removesuffix(".git")

        if self.enterprise_url:
            domain = self.enterprise_url
        else:
            domain = "github.com"

        ssh_prefix = f"git@{domain}:"

        if repo.startswith(domain):
            return True, repo.removeprefix(domain).removeprefix("/")

        if repo.startswith(ssh_prefix):
            return True, repo.removeprefix(ssh_prefix)

        splits = repo.split("/")
        if len(splits) == 2:
            return True, repo

        return False, None

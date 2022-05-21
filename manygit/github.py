import typing as T
from dataclasses import dataclass
from urllib.parse import urlsplit

import github3
from github3.exceptions import GitHubException, TransportError
from github3.git import Tag as Github3Tag
from github3.pulls import ShortPullRequest as Github3ShortPullRequest
from github3.repos.branch import Branch as Github3FullBranch
from github3.repos.branch import ShortBranch as Github3ShortBranch
from github3.repos.commit import RepoCommit as Github3RepoCommit
from github3.repos.commit import ShortCommit as Github3ShortCommit
from github3.repos.release import Release as Github3Release
from github3.repos.repo import Repository as Github3Repository
from github3.repos.status import Status as Github3Status
from github3.repos.tag import RepoTag as Github3RepoTag

from manygit.utils import parse_common_repo_formats

from .connections import connection
from .exceptions import (
    ManygitException,
    NetworkError,
    NotFoundError,
    VCSException,
    map_exceptions,
)
from .types import (
    Branch,
    Commit,
    CommitStatus,
    CommitStatusEnum,
    Connection,
    PullRequest,
    Release,
    Repository,
    Tag,
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

    commit_status: Github3Status

    def __init__(self, commit_status: Github3Status):
        self.commit_status = commit_status

    @property
    def name(self) -> str:
        return self.commit_status.context

    @property
    def status(self) -> CommitStatusEnum:
        return commit_status_from_github_status(self.commit_status.state)

    @property
    def data(self) -> str:
        return self.commit_status.description

    @property
    def url(self) -> T.Optional[str]:
        return self.commit_status.target_url


def commit_status_from_github_status(status: str) -> CommitStatusEnum:
    if status == "pending":
        return CommitStatusEnum.PENDING
    elif status in ["failure", "error"]:
        return CommitStatusEnum.FAILED
    elif status == "success":
        return CommitStatusEnum.SUCCESS

    raise ManygitException(f"Invalid commit status value {str}")


def commit_status_to_github_status(status: CommitStatusEnum) -> str:
    if status == CommitStatusEnum.PENDING:
        return "pending"
    elif status == CommitStatusEnum.FAILED:
        return "failure"
    elif status == CommitStatusEnum.SUCCESS:
        return "success"


GitHub3Commit = T.Union[Github3ShortCommit, Github3RepoCommit]


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
    def statuses(self) -> T.Iterator[CommitStatus]:
        for s in self.commit.statuses():
            yield GitHubCommitStatus(T.cast(Github3Status, s))

    def download(self):
        raise NotImplementedError

    @property
    @exc
    def parents(self) -> T.Iterator[Commit]:
        for c in self.commit.parents:
            yield self.repo.get_commit(c["sha"])

    @exc
    def set_commit_status(
        self,
        state: CommitStatusEnum,
        name: str,
        description: T.Optional[str],
        url: T.Optional[str],
    ):
        self.repo.repo.create_status(
            sha=self.sha,
            state=commit_status_to_github_status(state),
            target_url=url,
            description=description,
            context=name,
        )


Github3Branch = T.Union[Github3ShortBranch, Github3FullBranch]


class GitHubBranch(Branch):
    __slots__ = ["branch", "repo"]

    branch: Github3Branch
    repo: "GitHubRepository"

    def __init__(self, branch: Github3Branch, repo: "GitHubRepository"):
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
        return GitHubCommit(
            T.cast(Github3RepoCommit, self.branch.commit.refresh()), self.repo
        )


Github3AnyTag = T.Union[Github3RepoTag, Github3Tag]


class GitHubTag(Tag):
    __slots__ = ["tag"]

    tag: Github3AnyTag
    repo: "GitHubRepository"

    def __init__(self, tag: Github3AnyTag, repo: "GitHubRepository"):
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

    release: Github3Release
    repo: "GitHubRepository"

    def __init__(self, release: Github3Release, repo: "GitHubRepository"):
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

    pull_request: Github3ShortPullRequest
    repo: "GitHubRepository"

    def __init__(self, pull_request: Github3ShortPullRequest, repo: "GitHubRepository"):
        self.pull_request = pull_request
        self.repo = repo

    @property
    def base(self) -> Branch:
        return self.repo.get_branch(self.pull_request.base.ref)

    @property
    def source(self) -> Branch:
        return self.repo.get_branch(self.pull_request.head.ref)

    @exc
    def merge(self):
        self.pull_request.session.put(self.pull_request.url + "/merge")


class GitHubRepository(Repository):
    __slots__ = ["repo"]

    repo: Github3Repository

    def __init__(self, repo: Github3Repository):
        self.repo = repo

    @property
    def commits(self) -> T.Iterator[GitHubCommit]:
        raise NotImplementedError

    @exc
    def get_commit(self, sha: str) -> GitHubCommit:
        commit = self.repo.commit(sha)
        if not commit:
            raise NotFoundError
        return GitHubCommit(commit, self)

    @property
    @exc
    def branches(self) -> T.Iterator[GitHubBranch]:
        for branch in self.repo.branches():
            yield self.get_branch(T.cast(Github3ShortBranch, branch).name)

    @exc
    def get_branch(self, name: str) -> GitHubBranch:
        branch = self.repo.branch(name)
        if not branch:
            raise NotFoundError

        return GitHubBranch(branch, self)

    @property
    @exc
    def default_branch(self) -> GitHubBranch:
        return self.get_branch(self.repo.default_branch)

    @property
    @exc
    def tags(self) -> T.Iterator[GitHubTag]:
        for t in self.repo.tags():
            yield GitHubTag(T.cast(Github3RepoTag, t), self)

    @exc
    def get_tag(self, name: str) -> GitHubTag:
        ref = self.repo.ref(f"tags/{name}")
        if not ref:
            raise NotFoundError
        tag = self.repo.tag(ref.object.sha)
        if not tag:
            raise NotFoundError

        return GitHubTag(tag, self)

    @property
    @exc
    def releases(self) -> T.Iterator[GitHubRelease]:
        for r in self.repo.releases():
            yield GitHubRelease(T.cast(Github3Release, r), self)

    @exc
    def get_release(self, tag_name: str) -> GitHubRelease:
        release = self.repo.release_from_tag(tag_name)
        if not release:
            raise NotFoundError
        return GitHubRelease(release, self)

    @property
    @exc
    def pull_requests(self) -> T.Iterator[GitHubPullRequest]:
        for pr in self.repo.pull_requests(state="open"):
            yield GitHubPullRequest(T.cast(Github3ShortPullRequest, pr), self)

    @exc
    def merge_branches(self, base: GitHubBranch, source: GitHubBranch) -> bool:
        if base.repo != self or source.repo != self:
            raise ManygitException("Branches must be associated with the same repo")

        try:
            self.repo.merge(base.name, source.head.sha)
        except github3.exceptions.GitHubError as e:
            if e.code != 422:
                raise

            return False

        return True

    @exc
    def create_tag(
        self,
        tag_name: str,
        commit: GitHubCommit,
        message: str,
    ) -> GitHubTag:
        t = self.repo.create_tag(
            tag=tag_name,
            message=message,
            sha=commit.sha,
            obj_type="commit",
            tagger={"name": "manygit", "email": "manygit@example.com"},  # TODO
        )
        if not t:
            raise VCSException

        return GitHubTag(t, self)

    @exc
    def create_release(
        self,
        tag: Tag,
        name: str,
        body: T.Optional[str],
        is_prerelease: bool = False,
        is_draft: bool = False,
    ) -> GitHubRelease:
        release = self.repo.create_release(
            tag_name=tag.name,
            name=name,
            body=body,
            prerelease=is_prerelease,
            draft=is_draft,
        )
        if not release:
            raise VCSException
        return GitHubRelease(release, self)

    @exc
    def create_pull_request(
        self,
        title: str,
        base: Branch,
        source: Branch,
        body: T.Optional[str],
    ) -> GitHubPullRequest:
        pr = self.repo.create_pull(
            title=title, base=base.name, head=source.name, body=body
        )
        # raises UnprocessableEntity 422
        if not pr:
            raise VCSException

        return GitHubPullRequest(pr, self)


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
            self.enterprise_url = urlsplit(auth.enterprise_url).netloc
        else:
            self.conn = github3.github.GitHub(**args)
            self.enterprise_url = None

    @exc
    def get_repo(self, repo: str) -> GitHubRepository:
        repository = self.conn.repository(*repo.split("/"))
        if not repository:
            raise NotFoundError
        return GitHubRepository(repository)

    def is_eligible_repo(self, repo: str) -> T.Tuple[bool, T.Optional[str]]:
        if self.enterprise_url:
            domain = self.enterprise_url
        else:
            domain = "github.com"

        return parse_common_repo_formats(repo, domain)

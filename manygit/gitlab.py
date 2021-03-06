import typing as T
from dataclasses import dataclass
from urllib.parse import urlsplit

from gitlab.client import Gitlab
from gitlab.exceptions import GitlabGetError
from gitlab.v4.objects import (
    Project,
    ProjectBranch,
    ProjectCommit,
    ProjectCommitStatus,
    ProjectMergeRequest,
    ProjectRelease,
    ProjectTag,
)

from manygit.utils import parse_common_repo_formats

from .connections import connection
from .exceptions import (
    ManygitException,
    NotFoundError,
    UnsupportedException,
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

GITLAB_HOST = "GITLAB"


@dataclass
class GitLabOAuthTokenAuth:
    oauth_token: str
    enterprise_url: T.Optional[str] = None


@dataclass
class GitLabPersonalAccessTokenAuth:
    personal_access_token: str
    enterprise_url: T.Optional[str] = None


def commit_status_from_gitlab(status: str) -> CommitStatusEnum:
    if status in ["pending", "running"]:
        return CommitStatusEnum.PENDING
    elif status in ["failed", "canceled"]:
        return CommitStatusEnum.FAILED
    elif status == "success":
        return CommitStatusEnum.SUCCESS

    raise ManygitException(f"Invalid commit status value {str}")


def commit_status_to_gitlab(status: CommitStatusEnum) -> str:
    if status is CommitStatusEnum.PENDING:
        return "pending"
    elif status is CommitStatusEnum.FAILED:
        return "failed"
    elif status is CommitStatusEnum.SUCCESS:
        return "success"


exc = map_exceptions(
    {lambda e: isinstance(e, GitlabGetError) and e.response_code == 404: NotFoundError}
)


class GitLabCommitStatus(CommitStatus):
    __slots__ = ["commit_status"]

    commit_status: ProjectCommitStatus

    def __init__(self, commit_status: ProjectCommitStatus):
        self.commit_status = commit_status

    @property
    def name(self) -> str:
        return self.commit_status.name

    @property
    def status(self) -> CommitStatusEnum:
        return commit_status_from_gitlab(self.commit_status.status)

    @property
    def data(self) -> T.Optional[str]:
        return None

    @property
    def url(self) -> T.Optional[str]:
        return self.commit_status.target_url


class GitLabCommit(Commit):
    __slots__ = ["commit"]

    commit: ProjectCommit

    def __init__(self, commit: ProjectCommit):
        self.commit = commit

    @property
    def sha(self) -> str:
        return self.commit.id

    @property
    @exc
    def statuses(self) -> T.Iterator[CommitStatus]:
        for cs in self.commit.statuses.list(all=True, as_list=False):
            yield GitLabCommitStatus(T.cast(ProjectCommitStatus, cs))

    def download(self):
        raise NotImplementedError

    @property
    def parents(self) -> T.Iterator["GitLabCommit"]:
        for c in self.commit.parent_ids:
            yield GitLabCommit(self.commit.manager.get(c))  # type: ignore

    @exc
    def set_commit_status(
        self,
        state: CommitStatusEnum,
        name: str,
        description: T.Optional[str],
        url: T.Optional[str],
    ):

        self.commit.statuses.create(
            {
                "name": name,
                "description": description,
                "target_url": url,
                "state": commit_status_to_gitlab(state),
            }
        )


class GitLabBranch(Branch):
    __slots__ = ["branch", "repo"]
    branch: ProjectBranch
    repo: "GitLabRepository"

    def __init__(self, branch: ProjectBranch, repo: "GitLabRepository"):
        self.branch = branch
        self.repo = repo

    @property
    def name(self) -> str:
        return self.branch.name

    @property
    @exc
    def head(self) -> GitLabCommit:
        return self.repo.get_commit(self.branch.commit["id"])


class GitLabTag(Tag):
    __slots__ = ["tag", "repo"]

    tag: ProjectTag
    repo: "GitLabRepository"

    def __init__(self, tag: ProjectTag, repo: "GitLabRepository"):
        self.tag = tag
        self.repo = repo

    @property
    def name(self) -> str:
        return self.tag.name

    @property
    def commit(self) -> GitLabCommit:
        return self.repo.get_commit(self.tag.target)

    @property
    def annotation(self) -> str:
        return self.tag.message


class GitLabRelease(Release):
    __slots__ = ["repo", "release"]

    repo: "GitLabRepository"
    release: ProjectRelease

    def __init__(self, release: ProjectRelease, repo: "GitLabRepository"):
        self.repo = repo
        self.release = release

    @property
    def tag(self) -> GitLabTag:
        return self.repo.get_tag(self.release.tag_name)

    @property
    def name(self) -> str:
        return self.release.name

    @property
    def body(self) -> str:
        return self.release.description

    @property
    def commit(self) -> GitLabCommit:
        return self.repo.get_commit(self.release.commit["id"])


class GitLabPullRequest(PullRequest):
    pr: ProjectMergeRequest
    repo: "GitLabRepository"

    def __init__(self, pr: ProjectMergeRequest, repo: "GitLabRepository"):
        self.pr = pr
        self.repo = repo

    @property
    def base(self) -> Branch:
        return self.repo.get_branch(self.pr.target_branch)

    @property
    def source(self) -> Branch:
        return self.repo.get_branch(self.pr.source_branch)

    @exc
    def merge(self):
        self.pr.merge()


class GitLabRepository(Repository):
    __slots__ = ["repo"]

    repo: Project

    def __init__(self, repo: Project):
        self.repo = repo

    @property
    @exc
    def commits(self) -> T.Iterator[GitLabCommit]:
        for c in self.repo.commits.list(all=True, as_list=False):
            yield GitLabCommit(T.cast(ProjectCommit, c))

    @exc
    def get_commit(self, sha: str) -> GitLabCommit:
        return GitLabCommit(self.repo.commits.get(id=sha))

    @property
    @exc
    def branches(self) -> T.Iterator[GitLabBranch]:
        for b in self.repo.branches.list(all=True, as_list=False):
            yield GitLabBranch(T.cast(ProjectBranch, b), self)

    @exc
    def get_branch(self, name: str) -> GitLabBranch:
        return GitLabBranch(self.repo.branches.get(name), self)

    @property
    def default_branch(self) -> GitLabBranch:
        return self.get_branch(self.repo.default_branch)

    @property
    @exc
    def tags(self) -> T.Iterator[GitLabTag]:
        for t in self.repo.tags.list(all=True, as_list=False):
            yield GitLabTag(T.cast(ProjectTag, t), self)

    @exc
    def get_tag(self, name: str) -> GitLabTag:
        return GitLabTag(self.repo.tags.get(name), self)

    @property
    @exc
    def releases(self) -> T.Iterator[GitLabRelease]:
        for r in self.repo.releases.list(all=True, as_list=False):
            yield GitLabRelease(T.cast(ProjectRelease, r), self)

    @exc
    def get_release(self, name: str) -> GitLabRelease:
        return GitLabRelease(self.repo.releases.get(name), self)

    @property
    @exc
    def pull_requests(self) -> T.Iterator[GitLabPullRequest]:
        for pr in self.repo.mergerequests.list(all=True, as_list=False, state="opened"):
            yield GitLabPullRequest(T.cast(ProjectMergeRequest, pr), self)

    def merge_branches(self, base: GitLabBranch, source: GitLabBranch):
        # The GitLab API does not appear to support merging branches
        # absent a Merge Request.
        raise UnsupportedException(
            "GitLab repos do not support branch merging via API."
        )

    @exc
    def create_tag(
        self,
        tag_name: str,
        commit: Commit,
        message: str,
    ) -> GitLabTag:
        tag = self.repo.tags.create(
            {"tag_name": tag_name, "ref": commit.sha, "message": message}
        )
        return GitLabTag(T.cast(ProjectTag, tag), self)

    @exc
    def create_release(
        self,
        tag: GitLabTag,
        name: str,
        body: T.Optional[str],
        is_prerelease: bool = False,
        is_draft: bool = False,
    ) -> GitLabRelease:
        # GitLab does not (as far as I know) support draft or prerelease flags
        release = T.cast(
            ProjectRelease,
            self.repo.releases.create(
                {
                    "name": name,
                    "tag_name": tag.name,
                    "description": body,
                }
            ),
        )

        return GitLabRelease(release, self)

    @exc
    def create_pull_request(
        self,
        title: str,
        base: Branch,
        source: Branch,
        body: T.Optional[str],
    ) -> GitLabPullRequest:
        pr = T.cast(
            ProjectMergeRequest,
            self.repo.mergerequests.create(
                {
                    "source_branch": source.name,
                    "target_branch": base.name,
                    "title": title,
                    "description": body,
                }
            ),
        )

        return GitLabPullRequest(pr, self)


GitLabAuth = T.Union[GitLabOAuthTokenAuth, GitLabPersonalAccessTokenAuth]


@connection(
    host=GITLAB_HOST, auth_classes=[GitLabOAuthTokenAuth, GitLabPersonalAccessTokenAuth]
)
class GitLabConnection(Connection):
    __slots__ = ["conn", "enterprise_url"]

    conn: Gitlab
    enterprise_url: T.Optional[str]

    def __init__(self, auth: GitLabAuth):
        if isinstance(auth, GitLabPersonalAccessTokenAuth):
            args = {"private_token": auth.personal_access_token}
        else:
            args = {"oauth_token": auth.oauth_token}

        if auth.enterprise_url:
            self.conn = Gitlab(url=auth.enterprise_url, **args)
            self.enterprise_url = urlsplit(auth.enterprise_url).netloc
        else:
            self.conn = Gitlab(**args)
            self.enterprise_url = None

    @exc
    def get_repo(self, repo: str) -> GitLabRepository:
        return GitLabRepository(self.conn.projects.get(repo))

    def is_eligible_repo(self, repo: str) -> T.Tuple[bool, T.Optional[str]]:
        if self.enterprise_url:
            domain = self.enterprise_url
        else:
            domain = "gitlab.com"

        return parse_common_repo_formats(repo, domain)

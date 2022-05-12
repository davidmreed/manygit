from dataclasses import dataclass
import typing as T

import gitlab.v4.objects

from .types import (
    Connection,
    Branch,
    Commit,
    Tag,
    Release,
    CommitStatus,
    PullRequest,
    Repository,
    connection
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


class GitLabCommitStatus(CommitStatus):
    __slots__ = ['commit_status']

    commit_status: gitlab.v4.objects.ProjectCommitStatus

    def __init__(self, commit_status: gitlab.v4.objects.ProjectCommitStatus):
        self.commit_status = commit_status
    
    @property
    def name(self) -> str:
        return self.commit_status.name

    @property
    def status(self) -> str:
        return self.commit_status.status

    @property
    def data(self) -> T.Optional[str]:
        return None

    @property
    def url(self) -> T.Optional[str]:
        return self.commit_status.target_url


class GitLabCommit(Commit):
    __slots__ = ['commit']

    commit: gitlab.v4.objects.ProjectCommitStatus

    def __init__(self, commit: gitlab.v4.objects.ProjectCommitStatus):
        self.commit = commit

    @property
    def sha(self) -> str:
        return self.commit.id

    @property
    def statuses(self) -> T.Iterable[CommitStatus]:
        for cs in self.commit.statuses.list(all=True, as_list=False):
            yield GitLabCommitStatus(cs)

    def download(self):
        pass

    @property
    def parents(self) -> T.Iterable["GitLabCommit"]:
        for c in self.commit.parent_ids:
            yield GitLabCommit(self.commit.manager.get(c))


class GitLabBranch(Branch):
    __slots__ = ["branch", "repo"]
    branch: gitlab.v4.objects.ProjectBranch
    repo: 'GitLabRepository'

    def __init__(self, branch: gitlab.v4.objects.ProjectBranch, repo: 'GitLabRepository'):
        self.branch = branch
        self.repo = repo

    @property
    def name(self) -> str:
        return self.branch.name

    @property
    def head(self) -> GitLabCommit:
        return self.repo.get_commit(self.branch.commit['id'])


class GitLabTag(Tag):
    __slots__ = ["tag", "repo"]

    tag: gitlab.v4.objects.tags.ProjectTag
    repo: 'GitLabRepository'

    def __init__(self, tag: gitlab.v4.objects.tags.ProjectTag, repo: 'GitLabRepository'):
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
    __slots__ = ['repo', 'release']

    repo: 'GitLabRepository'
    release: gitlab.v4.objects.ProjectRelease

    def __init__(self, release: gitlab.v4.objects.ProjectRelease, repo: 'GitLabRepository'):
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
        return self.repo.get_commit(self.release.commit['id'])



class GitLabPullRequest(PullRequest):
    pr: gitlab.v4.objects.ProjectMergeRequest
    repo: 'GitLabRepository'

    def __init__(self, pr: gitlab.v4.objects.ProjectMergeRequest, repo: 'GitLabRepository'):
        self.pr = pr 
        self.repo = repo

    @property
    def base(self) -> Branch:
        return self.repo.get_branch(self.pr.target_branch)

    @property
    def source(self) -> Branch:
        return self.repo.get_branch(self.pr.source_branch)


class GitLabRepository(Repository):
    __slots__ = ["repo"]

    repo: gitlab.v4.objects.Project

    def __init__(self, repo: gitlab.v4.objects.Project):
        self.repo = repo

    @property
    def commits(self) -> T.Iterable[GitLabCommit]:
        for c in self.repo.commits.list(all=True, as_list=False):
            yield GitLabCommit(c)

    def get_commit(self, sha: str) -> GitLabCommit:
        return GitLabCommit(self.repo.commits.get(id=sha))

    @property
    def branches(self) -> T.Iterable[GitLabBranch]:
        for b in self.repo.branches.list(all=True, as_list=False):
            yield GitLabBranch(b, self)

    def get_branch(self, name: str) -> GitLabBranch:
        return GitLabBranch(self.repo.branches.get(name), self)

    @property
    def default_branch(self) -> GitLabBranch:
        return self.get_branch(self.repo.default_branch)

    @property
    def tags(self) -> T.Iterable[GitLabTag]:
        for t in self.repo.tags.list(all=True, as_list=False):
            yield GitLabTag(t, self)

    def get_tag(self, name: str) -> GitLabTag:
        return GitLabTag(self.repo.tags.get(name), self)

    @property
    def releases(self) -> T.Iterable[GitLabRelease]:
        for r in self.repo.releases.list(all=True, as_list=False):
            yield GitLabRelease(r, self)

    def get_release(self, name: str) -> GitLabRelease:
        return GitLabRelease(self.repo.releases.get(name), self)

    @property
    def pull_requests(self) -> T.Iterable[GitLabPullRequest]:
        for pr in self.repo.mergerequests.list(all=True, as_list=False):
            yield GitLabPullRequest(pr, self)


GitLabAuth = T.Union[GitLabOAuthTokenAuth, GitLabPersonalAccessTokenAuth]


@connection(host=GITLAB_HOST, auth_classes=[GitLabOAuthTokenAuth, GitLabPersonalAccessTokenAuth])
class GitLabConnection(Connection):
    __slots__ = []

    conn: gitlab.Gitlab
    enterprise_url: T.Optional[str]

    auth_type = GitLabAuth
    host = GITLAB_HOST

    def __init__(self, auth: GitLabAuth):
        if isinstance(auth, GitLabPersonalAccessTokenAuth):
            args = {"private_token": auth.personal_access_token}
        else:
            args = {"oauth_token": auth.oauth_token}

        if auth.enterprise_url:
            self.conn = gitlab.Gitlab(url=auth.enterprise_url, **args)
            self.enterprise_url = auth.enterprise_url
        else:
            self.conn = gitlab.Gitlab(**args)
            self.enterprise_url = None

    def get_repo(self, repo: str) -> GitLabRepository:
        return GitLabRepository(self.conn.projects.get(repo))

    def is_eligible_repo(self, repo: str) -> T.Tuple[bool, T.Optional[str]]:
        # GitLab URL patterns
        # https://gitlab.com/davidmreed/amaxa
        # git@gitlab.com:davidmreed/amaxa.git
        # TODO: GitLab Enterprise
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

        if repo.startswith("git@gitlab.com:"):
            return True, repo.removeprefix("git@gitlab.com:")

        if repo.startswith("gitlab.com/"):
            return True, repo.removeprefix("gitlab.com/")

        splits = repo.split("/")
        if len(splits) == 2:
            return True, repo

        return False, None

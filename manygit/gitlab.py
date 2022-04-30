import gitlab.v4.objects

import typing as T


from .types import (
    Connection,
    Branch,
    Commit,
    Tag,
    Release,
    CommitStatus,
    Commit,
    PullRequest,
    Repository,
    GitLabOAuthTokenAuth,
    GitLabPersonalAccessTokenAuth,
)


class GitLabCommitStatus(CommitStatus):
    @property
    def name(self) -> str:
        pass

    @property
    def status(self) -> str:
        pass

    @property
    def data(self) -> str:
        pass


class GitLabCommit(Commit):
    @property
    def sha(self) -> str:
        pass

    @property
    def statuses(self) -> T.Iterable[CommitStatus]:
        pass

    def download(self):
        pass

    @property
    def parents(self) -> T.Iterable["Commit"]:
        pass


class GitLabBranch(Branch):
    __slots__ = ["branch"]
    branch: gitlab.v4.objects.ProjectBranch

    def __init__(self, branch):
        self.branch = branch

    @property
    def name(self) -> str:
        return self.branch.name

    @property
    def head(self) -> Commit:
        pass


class GitLabTag(Tag):
    @property
    def name(self) -> str:
        pass

    @property
    def commit(self) -> GitLabCommit:
        pass

    @property
    def annotation(self) -> str:
        pass


class GitLabRelease(Release):
    @property
    def tag(self) -> GitLabTag:
        pass

    @property
    def title(self) -> str:
        pass

    @property
    def body(self) -> str:
        pass

    @property
    def commit(self) -> GitLabCommit:
        return self.tag.commit

    # TODO: Release Assets


class GitLabPullRequest(PullRequest):
    @property
    def base(self) -> Branch:
        pass

    @property
    def target(self) -> Branch:
        pass


class GitLabRepository(Repository):
    __slots__ = ["repo"]

    repo: gitlab.v4.objects.Project

    def __init__(self, repo: gitlab.v4.objects.Project):
        self.repo = repo

    def branches(self) -> T.Iterable[GitLabBranch]:
        for b in self.repo.branches.iter():
            yield GitLabBranch(b)

    def get_branch(self, name: str) -> GitLabBranch:
        return GitLabBranch(self.repo.branches.get(name))

    @property
    def default_branch(self) -> GitLabBranch:
        return self.get_branch(self.repo.default_branch)

    def tags(self) -> T.Iterable[GitLabTag]:
        pass

    def get_tag(self, name: str) -> GitLabTag:
        pass

    def releases(self) -> T.Iterable[GitLabRelease]:
        pass

    def get_release(self, name: str) -> GitLabRelease:
        pass


GitLabAuth = T.Union[GitLabOAuthTokenAuth, GitLabPersonalAccessTokenAuth]


class GitLabConnection(Connection):
    conn: gitlab.Gitlab

    enterprise_url: T.Optional[str]

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

    def is_eligible_repo(self, repo: str) -> T.Tuple[bool, str]:
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

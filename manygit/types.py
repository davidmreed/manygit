import abc
import typing as T
import enum
import pydantic


class CommitStatus(abc.ABC):
    @property
    def name(self) -> str:
        pass

    @property
    def status(self) -> str:
        pass

    @property
    def data(self) -> str:
        pass


class Commit(abc.ABC):
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


class Branch(abc.ABC):
    @property
    def name(self) -> str:
        pass

    @property
    def head(self) -> Commit:
        pass


class Tag(abc.ABC):
    @property
    def name(self) -> str:
        pass

    @property
    def commit(self) -> Commit:
        pass

    @property
    def annotation(self) -> str:
        pass


class Release(abc.ABC):
    @property
    def tag(self) -> Tag:
        pass

    @property
    def title(self) -> str:
        pass

    @property
    def body(self) -> str:
        pass

    @property
    def commit(self) -> Commit:
        return self.tag.commit

    # TODO: Release Assets


class PullRequest(abc.ABC):
    @property
    def base(self) -> Branch:
        pass

    @property
    def target(self) -> Branch:
        pass


class Repository(abc.ABC):
    __slots__ = []

    def branches(self) -> T.Iterable[Branch]:
        pass

    def get_branch(self, name: str) -> Branch:
        pass

    @property
    def default_branch(self) -> Branch:
        pass

    def tags(self) -> T.Iterable[Tag]:
        pass

    def get_tag(self, name: str) -> Tag:
        pass

    def releases(self) -> T.Iterable[Release]:
        pass

    def get_release(self, name: str) -> Release:
        pass


class Connection(abc.ABC):
    def is_eligible_repo(self, repo: str) -> bool:
        pass

    def get_repo(self, repo: str) -> Repository:
        pass


class GitHost(str, enum.Enum):
    GITHUB = "GitHub"
    GITLAB = "GitLab"
    BITBUCKET = "BitBucket"
    GITEA = "Gitea"
    AZURE_DEVOPS = "Azure DevOps"


class GitHubOAuthTokenAuth(pydantic.BaseModel):
    oauth_token: str
    enterprise_url: T.Optional[str]


class GitHubPersonalAccessTokenAuth(pydantic.BaseModel):
    username: str
    personal_access_token: str
    enterprise_url: T.Optional[str]


class GitLabOAuthTokenAuth(pydantic.BaseModel):
    oauth_token: str
    enterprise_url: T.Optional[str]


class GitLabPersonalAccessTokenAuth(pydantic.BaseModel):
    personal_access_token: str
    enterprise_url: T.Optional[str]


class RepositoryException(Exception):
    pass


class ConnectionManager:
    __slots__ = ["connections"]

    connections: dict[GitHost, Connection]

    def __init__(self, connections: T.Optional[dict[GitHost, Connection]] = None):
        self.connections = connections or {}

    def add_connection(self, host: GitHost, connection: Connection):
        self.connections[host] = connection

    def get_repo(self, repo: str, host_hint: T.Optional[GitHost] = None) -> Repository:
        """Given a string and an optional hint as to the host service,
        attempt to create a Repository instance."""

        host: Optional[GitHost] = None

        if host_hint and host_hint in self.connections:
            repo_eligible, repo_normalized = self.connections[
                host_hint
            ].is_eligible_repo(repo)
            if repo_eligible:
                return self.connections[host_hint].get_repo(repo_normalized)

        for conn in self.connections.values():
            repo_eligible, repo_normalized = conn.is_eligible_repo(repo)
            if repo_eligible:
                return conn.get_repo(repo_normalized)

        raise RepositoryException(
            f"No available connections accept the repo specification {repo}"
        )
        # BitBucket URL patterns
        # https://bitbucket.org/davidreed/amaxa/src/master
        # git@bitbucket.org:davidreed/amaxa.git
        # https://davidreed@bitbucket.org/davidreed/amaxa.git

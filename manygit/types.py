import abc
import enum
import typing as T
from collections import defaultdict
from dataclasses import dataclass

from .exceptions import ConnectionException


class CommitStatusEnum(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class CommitStatus(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def status(self) -> CommitStatusEnum:
        ...

    @property
    @abc.abstractmethod
    def data(self) -> T.Optional[str]:
        ...

    @property
    @abc.abstractmethod
    def url(self) -> T.Optional[str]:
        ...


class Commit(abc.ABC):
    @property
    @abc.abstractmethod
    def sha(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def statuses(self) -> T.Iterable[CommitStatus]:
        ...

    @abc.abstractmethod
    def download(self):
        ...

    @property
    @abc.abstractmethod
    def parents(self) -> T.Iterable["Commit"]:
        ...


class Branch(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def head(self) -> Commit:
        ...


class Tag(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def commit(self) -> Commit:
        ...

    @property
    @abc.abstractmethod
    def annotation(self) -> str:
        ...


class Release(abc.ABC):
    @property
    @abc.abstractmethod
    def tag(self) -> Tag:
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def body(self) -> str:
        ...

    @property
    def commit(self) -> Commit:
        return self.tag.commit

    @property
    def is_draft(self) -> bool:
        return False

    @property
    def is_prerelease(self) -> bool:
        return False


class PullRequest(abc.ABC):
    # TODO: name, user, status, identifier

    @property
    @abc.abstractmethod
    def base(self) -> Branch:
        ...

    @property
    @abc.abstractmethod
    def source(self) -> Branch:
        ...


@dataclass
class PullRequestData:
    title: str
    base: Branch
    source: Branch
    body: T.Optional[str]


@dataclass
class TagData:
    tag_name: str
    commit: Commit
    message: str


@dataclass
class ReleaseData:
    tag: Tag
    name: str
    body: T.Optional[str]
    is_prerelease: bool = False
    is_draft: bool = False


@dataclass
class CommitStatusData:
    commit: Commit
    state: CommitStatusEnum
    url: T.Optional[str]
    name: str
    description: T.Optional[str]


class Repository(abc.ABC):
    __slots__ = []

    @property
    @abc.abstractmethod
    def commits(self) -> T.Iterable[Commit]:
        ...

    @abc.abstractmethod
    def get_commit(self, sha: str) -> Commit:
        ...

    @property
    @abc.abstractmethod
    def branches(self) -> T.Iterable[Branch]:
        ...

    @abc.abstractmethod
    def get_branch(self, name: str) -> Branch:
        ...

    @property
    @abc.abstractmethod
    def default_branch(self) -> Branch:
        ...

    @property
    @abc.abstractmethod
    def tags(self) -> T.Iterable[Tag]:
        ...

    @abc.abstractmethod
    def get_tag(self, name: str) -> Tag:
        ...

    @property
    @abc.abstractmethod
    def releases(self) -> T.Iterable[Release]:
        ...

    @abc.abstractmethod
    def get_release(self, name: str) -> Release:
        ...

    @property
    @abc.abstractmethod
    def pull_requests(self) -> T.Iterable[PullRequest]:
        ...

    @abc.abstractmethod
    def merge_branches(self, base: Branch, source: Branch):
        ...

    @abc.abstractmethod
    def set_commit_status(self, commit: Commit, commit_status: CommitStatusData):
        ...

    @abc.abstractmethod
    def create_tag(self, data: TagData) -> Tag:
        ...

    @abc.abstractmethod
    def create_release(self, data: ReleaseData) -> Release:
        ...

    @abc.abstractmethod
    def create_pull_request(self, data: PullRequestData) -> PullRequest:
        ...

    @abc.abstractmethod
    def merge_pull_request(self, pull_request: PullRequest):
        ...


class Connection(abc.ABC):
    @abc.abstractmethod
    def __init__(self, conn: T.Any):
        ...

    @abc.abstractmethod
    def is_eligible_repo(self, repo: str) -> T.Tuple[bool, T.Optional[str]]:
        ...

    @abc.abstractmethod
    def get_repo(self, repo: str) -> Repository:
        ...


connection_classes: dict[T.Type[T.Any], T.Type[Connection]] = {}
available_hosts: T.DefaultDict[str, list[T.Type[T.Any]]] = defaultdict(list)


def connection(*, host: str, auth_classes: list[T.Type[T.Any]]):
    def _connection(klass: T.Type[Connection]):
        for c in auth_classes:
            connection_classes[c] = klass

        available_hosts[host].extend(auth_classes)

    return _connection


def get_available_hosts() -> T.Iterable[str]:
    return available_hosts.keys()


class ConnectionManager:
    __slots__ = ["connections"]

    connections: list[T.Any]

    def __init__(self, connections: T.Optional[list[T.Any]] = None):
        self.connections = []
        for c in connections or []:
            self.add_connection(c)

    def add_connection(self, conn: T.Any):
        if type(conn) in connection_classes:
            connection_class = connection_classes[type(conn)]
            self.connections.append(connection_class(conn))
        else:
            raise ConnectionException(
                f"{conn} is not an instance of a Git host authentication class"
            )

    def get_repo(self, repo: str, host_hint: T.Optional[str] = None) -> Repository:
        """Given a string and an optional hint as to the host service,
        attempt to create a Repository instance."""

        eligible_classes = self.connections

        if host_hint and host_hint in available_hosts:
            eligible_classes = [
                t for t in self.connections if type(t) in available_hosts[host_hint]
            ]

        for conn in eligible_classes:
            repo_eligible, repo_normalized = conn.is_eligible_repo(repo)
            if repo_eligible:
                return conn.get_repo(repo_normalized)

        raise ConnectionException(
            f"No available connections accept the repo specification {repo}"
        )

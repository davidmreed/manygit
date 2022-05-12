import abc
import typing as T
from collections import defaultdict

try:
    import manygit.gitlab
except ImportError:
    pass

try:
    import manygit.github
except ImportError:
    pass


class ManygitException(Exception):
    pass

class CommitStatus(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def status(self) -> str:
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
    @abc.abstractmethod
    def commit(self) -> Commit:
        return self.tag.commit

    @property
    def is_draft(self) -> bool:
        return False

    @property
    def is_prerelease(self) -> bool:
        return False



class PullRequest(abc.ABC):
    @property
    @abc.abstractmethod
    def base(self) -> Branch:
        ...

    @property
    @abc.abstractmethod
    def source(self) -> Branch:
        ...


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


class RepositoryException(Exception):
    pass


connection_classes: dict[T.Type[T.Any], T.Type[Connection]] = {}
available_hosts: T.DefaultDict[str,list[T.Type[T.Any]]] = defaultdict(list)


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
            raise ManygitException(f"{conn} is not an instance of a Git host authentication class")

    def get_repo(self, repo: str, host_hint: T.Optional[str] = None) -> Repository:
        """Given a string and an optional hint as to the host service,
        attempt to create a Repository instance."""

        if host_hint and host_hint in self.connections:
            repo_eligible, repo_normalized = self.connections[
                host_hint
            ].is_eligible_repo(repo)
            if repo_eligible:
                return self.connections[host_hint].get_repo(repo_normalized)

        for conn in self.connections:
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

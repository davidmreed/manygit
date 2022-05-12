import abc
import typing as T
import enum
import pydantic
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
    def name(self) -> str:
        pass

    @property
    def body(self) -> str:
        pass

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
    @property
    def base(self) -> Branch:
        pass

    @property
    def source(self) -> Branch:
        pass


class Repository(abc.ABC):
    __slots__ = []

    @property
    def commits(self) -> T.Iterable[Commit]:
        pass

    def get_commit(self, sha: str) -> Commit:
        pass

    @property
    def branches(self) -> T.Iterable[Branch]:
        pass

    def get_branch(self, name: str) -> Branch:
        pass

    @property
    def default_branch(self) -> Branch:
        pass

    @property
    def tags(self) -> T.Iterable[Tag]:
        pass

    def get_tag(self, name: str) -> Tag:
        pass

    @property
    def releases(self) -> T.Iterable[Release]:
        pass

    def get_release(self, name: str) -> Release:
        pass

    @property
    def pull_requests(self) -> T.Iterable[PullRequest]:
        pass


class Connection(abc.ABC):
    def is_eligible_repo(self, repo: str) -> T.Tuple[bool, str]:
        pass

    def get_repo(self, repo: str) -> Repository:
        pass


class RepositoryException(Exception):
    pass


connection_classes = {}
available_hosts = defaultdict(list)


def connection(*, host: str, auth_classes: list[T.Type]):
    def _connection(klass: T.Type):
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

    def get_repo(self, repo: str, host_hint: T.Optional[GitHost] = None) -> Repository:
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

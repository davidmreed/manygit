import typing as T
from collections import defaultdict

from .exceptions import ConnectionException
from .types import Connection, Repository

connection_classes: dict[type, type[Connection]] = {}
available_hosts: T.DefaultDict[str, list[type]] = defaultdict(list)


def connection(*, host: str, auth_classes: list[type[T.Any]]):
    def _connection(klass: type[Connection]):
        for c in auth_classes:
            connection_classes[c] = klass

        available_hosts[host].extend(auth_classes)

        return klass

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

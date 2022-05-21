import abc
import enum
import typing as T


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
    def statuses(self) -> T.Iterator[CommitStatus]:
        ...

    @abc.abstractmethod
    def download(self):
        ...

    @property
    @abc.abstractmethod
    def parents(self) -> T.Iterator["Commit"]:
        ...

    @abc.abstractmethod
    def set_commit_status(
        self,
        state: CommitStatusEnum,
        name: str,
        description: T.Optional[str],
        url: T.Optional[str],
    ):
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

    @abc.abstractmethod
    def merge(self):
        ...


class Repository(abc.ABC):
    __slots__ = []

    @property
    @abc.abstractmethod
    def commits(self) -> T.Iterator[Commit]:
        ...

    @abc.abstractmethod
    def get_commit(self, sha: str) -> Commit:
        ...

    @property
    @abc.abstractmethod
    def branches(self) -> T.Iterator[Branch]:
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
    def tags(self) -> T.Iterator[Tag]:
        ...

    @abc.abstractmethod
    def get_tag(self, name: str) -> Tag:
        ...

    @property
    @abc.abstractmethod
    def releases(self) -> T.Iterator[Release]:
        ...

    @abc.abstractmethod
    def get_release(self, name: str) -> Release:
        ...

    @property
    @abc.abstractmethod
    def pull_requests(self) -> T.Iterator[PullRequest]:
        ...

    @abc.abstractmethod
    def merge_branches(self, base: Branch, source: Branch):
        ...

    @abc.abstractmethod
    def create_tag(
        self,
        tag_name: str,
        commit: Commit,
        message: str,
    ) -> Tag:
        ...

    @abc.abstractmethod
    def create_release(
        self,
        tag: Tag,
        name: str,
        body: T.Optional[str],
        is_prerelease: bool = False,
        is_draft: bool = False,
    ) -> Release:
        ...

    @abc.abstractmethod
    def create_pull_request(
        self,
        title: str,
        base: Branch,
        source: Branch,
        body: T.Optional[str],
    ) -> PullRequest:
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

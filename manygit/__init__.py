try:
    from manygit.gitlab import GitLabOAuthTokenAuth, GitLabPersonalAccessTokenAuth
except ImportError:
    pass

try:
    from manygit.github import GitHubOAuthTokenAuth, GitHubPersonalAccessTokenAuth
except ImportError:
    pass

from .connections import ConnectionManager
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

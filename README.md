# Manygit

Manygit provides a simple, fully-typed API to accomplish a subset of common Git operations across:

- GitHub
- GitHub Enterprise
- GitLab
- GitLab Enterprise

with more Git hosts planned for the future.

Manygit insulates clients from the details of different hosts by parsing HTTPS and SSH URLs for repos and connecting them to appropriate authenticated sessions provided by the client. Other than managing authentication, clients can be entirely agnostic to the host of repos on which they operate.

**Manygit is in alpha state**. Please wait for a stable release before using in production.

## Example

```
import os

from manygit.github import GitHubPersonalAccessTokenAuth
from manygit.gitlab import GitLabPersonalAccessTokenAuth
from manygit.types import CommitStatusEnum, ConnectionManager

# A ConnectionManager collates authenticated access
# across supported Git hosts.
cm = ConnectionManager()

# Add connections using Pydantic structs
cm.add_connection(
    GitLabPersonalAccessTokenAuth(
        personal_access_token=os.environ["GITLAB_ACCESS_TOKEN"],
    )
)
cm.add_connection(
    GitHubPersonalAccessTokenAuth(
        username=os.environ["GITHUB_USERNAME"],
        personal_access_token=os.environ["GITHUB_ACCESS_TOKEN"],
    )
)

# Now, we can add repos by URL (no parsing required)
gl = cm.get_repo("https://gitlab.com/davidmreed/manygit-test")
gh = cm.get_repo("git@github.com:davidmreed/manygit-test.git")

# And interact with them using a single, streamlined API.
for repo in [gl, gh]:
    if all(
        commit_status.status is CommitStatusEnum.SUCCESS
        for commit_status in repo.default_branch.head.statuses
    ):
        print(f"The commit {repo.default_branch.head.sha} passes!")
```

## Underlying Libraries

Manygit doesn't implement the API layer itself. It relies on widely-used libraries to interface with each Git host:

- GitHub: `github3.py`
- GitLab: `python-gitlab`

import typing as T


def parse_common_repo_formats(repo: str, domain: str) -> T.Tuple[bool, T.Optional[str]]:
    repo = repo.removeprefix("https://")
    repo = repo.removeprefix("ssh://")
    repo = repo.removesuffix(".git")

    ssh_prefix = f"git@{domain}:"

    if repo.startswith(domain):
        return True, repo.removeprefix(domain).removeprefix("/")

    if repo.startswith(ssh_prefix):
        return True, repo.removeprefix(ssh_prefix)

    if ":" not in repo:
        splits = repo.split("/")
        if len(splits) == 2:
            return True, repo

    return False, None

"""Small GitHub helpers shared by the agents."""

from __future__ import annotations

import re

from github import GithubException
from github.Repository import Repository

from foundry_core.shell import log


def references_issue(body: str | None, issue_number: int) -> bool:
    """True if a PR body references ``#<issue_number>`` (and not e.g. #123x)."""
    return bool(body) and re.search(rf"#{issue_number}(?:\D|$)", body) is not None


def ensure_label(repo: Repository, name: str, color: str = "ededed") -> None:
    try:
        repo.get_label(name)
    except GithubException as exc:
        if exc.status == 404:
            repo.create_label(name=name, color=color)
        else:
            log(f"ensure_label: unexpected error checking for {name!r}: {exc}")
            raise

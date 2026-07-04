"""Small GitHub helpers shared by the agents."""

from __future__ import annotations

import re

from github import GithubException
from github.Repository import Repository


def references_issue(body: str | None, issue_number: int) -> bool:
    """True if a PR body references ``#<issue_number>`` (and not e.g. #123x)."""
    return bool(body) and re.search(rf"#{issue_number}(?:\D|$)", body) is not None


def get_score_from_labels(issue) -> int | None:
    """Parse ``ice-N`` or ``rice-N`` label into a numeric score, or *None*."""
    for label in issue.labels:
        match = re.match(r"(?:ice|rice)-(\d+)", label.name)
        if match:
            return int(match.group(1))
    return None


def ensure_label(repo: Repository, name: str, color: str = "ededed") -> None:
    try:
        repo.get_label(name)
    except GithubException:
        repo.create_label(name=name, color=color)

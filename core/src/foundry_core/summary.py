"""Write a Markdown job summary to ``$GITHUB_STEP_SUMMARY``.

The helper gracefully no-ops when the variable is not set (local development).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class RunResult:
    """Structured outcome of an agent run."""

    agent: str
    version: str
    action: str
    url: str | None = None
    duration_s: float = 0.0
    model: str = ""
    warnings: list[str] = field(default_factory=list)


def _format_duration(seconds: float) -> str:
    """Return a human-readable duration like '3m 42s' or '12s'."""
    if seconds < 0:
        seconds = 0.0
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def write_summary(result: RunResult) -> None:
    """Append a Markdown summary card to ``$GITHUB_STEP_SUMMARY``.

    No-ops when the env var is absent (local dev) or on any I/O error.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return

    duration = _format_duration(result.duration_s)

    lines: list[str] = []
    lines.append(f"### {result.agent}-agent run completed\n")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| **Action** | {result.action} |")
    if result.url:
        lines.append(f"| **Link** | {result.url} |")
    lines.append(f"| **Duration** | {duration} |")
    if result.model:
        lines.append(f"| **Model** | {result.model} |")

    if result.warnings:
        lines.append("")
        lines.append("<details><summary>Warnings</summary>")
        lines.append("")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")
        lines.append("</details>")

    lines.append("")  # trailing newline

    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    except OSError:
        pass

"""Pluggable harness protocol for agent-foundry.

A *harness* is any coding agent that can execute prompts non-interactively.
Every agent talks to its harness through the same two-method interface defined
here.  The :func:`get_harness` factory selects the implementation based on
the ``HARNESS`` environment variable (default ``"opencode"``).
"""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable


@runtime_checkable
class Harness(Protocol):
    """Minimal interface every coding-agent driver must satisfy."""

    def run(
        self,
        prompt: str,
        *,
        agent: str | None = None,
        continue_session: bool = False,
    ) -> None:
        """Execute *prompt* non-interactively on the coding agent."""
        ...

    def plan_then_build(
        self,
        context: str,
        build_instructions: str,
        *,
        plan_instructions: str,
        build_lead_in: str,
    ) -> None:
        """Plan/research (read-only) then act, or a single pass if disabled."""
        ...


def get_harness() -> Harness:
    """Instantiate the harness selected by the ``HARNESS`` env var.

    Supported values: ``"opencode"`` (default), ``"claude-code"``.
    """
    from foundry_core.config import env  # local to avoid circular import

    name = env("HARNESS", "opencode").lower().replace("-", "_")

    if name == "opencode":
        from foundry_core.opencode import Opencode

        return Opencode.from_env()

    if name == "claude_code":
        from foundry_core.claude_code import ClaudeCode

        return ClaudeCode.from_env()

    sys.exit(
        f"Unknown harness {env('HARNESS', 'opencode')!r}. "
        "Supported harnesses: opencode, claude-code."
    )

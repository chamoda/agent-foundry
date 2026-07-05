"""Claude Code harness: run prompts via the ``claude`` CLI.

This module implements the :class:`~foundry_core.harness.Harness` protocol
backed by the `Claude Code <https://docs.anthropic.com/en/docs/claude-code>`_
CLI (``claude -p``).  It reads environment variables for configuration and
executes the same two-phase plan-then-build pattern the agents expect.

Environment variables:

* ``CLAUDE_MODEL`` — model id (default ``claude-sonnet-4-20250514``).
* ``CLAUDE_PERMISSION_MODE`` — permission mode (default ``bypassPermissions``).
* ``OPENCODE_PLAN`` — whether to plan first (shared with the opencode harness;
  default ``true``).
* ``OPENCODE_TIMEOUT`` — per-pass timeout in seconds (default ``3600``).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from foundry_core.config import env, env_bool, env_int
from foundry_core.shell import log, run

DEFAULT_MODEL = "claude-sonnet-4-20250514"


@dataclass(frozen=True)
class ClaudeCode:
    """How to invoke the ``claude`` CLI, read once from the environment."""

    model: str = DEFAULT_MODEL
    permission_mode: str = "bypassPermissions"
    plan_first: bool = True
    timeout_s: int = 3600

    @classmethod
    def from_env(cls) -> ClaudeCode:
        return cls(
            model=env("CLAUDE_MODEL", DEFAULT_MODEL),
            permission_mode=env("CLAUDE_PERMISSION_MODE", "bypassPermissions"),
            plan_first=env_bool("OPENCODE_PLAN", True),
            timeout_s=env_int("OPENCODE_TIMEOUT", 3600),
        )

    def run(
        self,
        prompt: str,
        *,
        agent: str | None = None,
        continue_session: bool = False,
    ) -> None:
        cmd = ["claude", "-p", prompt]
        if self.model:
            cmd += ["--model", self.model]
        if self.permission_mode:
            cmd += ["--permission-mode", self.permission_mode]
        if continue_session:
            cmd += ["--continue"]
        log(
            f"Running claude (model={self.model}, "
            f"prompt={len(prompt)} chars)…"
        )
        try:
            run(cmd, timeout=self.timeout_s or None)
        except subprocess.TimeoutExpired:
            sys.exit(
                f"claude exceeded its {self.timeout_s}s timeout and was "
                "killed — the pass stalled. Raise OPENCODE_TIMEOUT if this "
                "was a legitimately long run."
            )

    def plan_then_build(
        self,
        context: str,
        build_instructions: str,
        *,
        plan_instructions: str,
        build_lead_in: str,
    ) -> None:
        """Plan/research (read-only) then act, or a single pass if disabled.

        ``plan_instructions`` is appended to the context for the read-only
        pass; ``build_lead_in`` prefixes the build pass that continues the
        session.
        """
        if self.plan_first:
            self.run(context + "\n\n" + plan_instructions)
            self.run(
                build_lead_in + "\n" + build_instructions,
                continue_session=True,
            )
        else:
            self.run(context + "\n\n" + build_instructions)

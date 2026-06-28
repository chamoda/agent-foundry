"""Claude Code driver: run prompts non-interactively via ``claude -p``.

Mirrors the :class:`~foundry_core.opencode.Opencode` interface so it can be
used as a drop-in harness behind :func:`~foundry_core.harness.get_harness`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass

from foundry_core.config import env, env_bool, env_int
from foundry_core.shell import log, run

DEFAULT_MODEL = "claude-sonnet-4-20250514"


@dataclass(frozen=True)
class ClaudeCode:
    """How to invoke Claude Code, read once from the environment."""

    model: str = DEFAULT_MODEL
    permission_mode: str = "bypassPermissions"
    plan_first: bool = True
    timeout_s: int = 3600

    @classmethod
    def from_env(cls) -> ClaudeCode:
        return cls(
            model=env("CLAUDE_MODEL", DEFAULT_MODEL),
            permission_mode=env("CLAUDE_PERMISSION_MODE", "bypassPermissions"),
            plan_first=env_bool("CLAUDE_PLAN", True),
            timeout_s=env_int("CLAUDE_TIMEOUT", 3600),
        )

    def run(
        self, prompt: str, *, agent: str | None = None, continue_session: bool = False
    ) -> None:
        cmd = [
            "claude",
            "-p",
            prompt,
            "--model",
            self.model,
            "--permission-mode",
            self.permission_mode,
        ]
        if continue_session:
            cmd.append("--continue")
        log(
            f"Running Claude Code (agent={agent or 'build'}, "
            f"model={self.model}, prompt={len(prompt)} chars)…"
        )
        try:
            run(cmd, timeout=self.timeout_s or None)
        except subprocess.TimeoutExpired:
            sys.exit(
                f"Claude Code (agent={agent or 'build'}) exceeded its "
                f"{self.timeout_s}s timeout and was killed — the pass stalled. "
                "Raise CLAUDE_TIMEOUT if this was a legitimately long run."
            )

    def plan_then_build(
        self,
        context: str,
        build_instructions: str,
        *,
        plan_instructions: str,
        build_lead_in: str,
    ) -> None:
        if self.plan_first:
            self.run(context + "\n\n" + plan_instructions, agent="plan")
            self.run(
                build_lead_in + "\n" + build_instructions,
                agent="build",
                continue_session=True,
            )
        else:
            self.run(context + "\n\n" + build_instructions, agent="build")

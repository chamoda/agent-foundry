"""The opencode driver: run prompts non-interactively, optionally plan-first.

Every agent talks to opencode the same way — a read-only ``plan`` pass that
researches, then a ``build`` pass that continues the same session and acts.
Only the wording of each pass differs per agent, so it is passed in.
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from foundry_core.config import env, env_bool, env_int
from foundry_core.shell import log, run

DEFAULT_MODEL = "opencode/mimo-v2.5-free"


@functools.cache
def _config_path() -> str:
    """Config so opencode runs fully non-interactively.

    The build agent may edit/bash/webfetch; the plan agent may explore (read,
    bash) but never edit, so the planning pass stays read-only.
    """
    config = {
        "$schema": "https://opencode.ai/config.json",
        "permission": {"edit": "allow", "bash": "allow", "webfetch": "allow"},
        "agent": {"plan": {"permission": {"edit": "deny", "bash": "allow"}}},
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump(config, fh)
    return path


@dataclass(frozen=True)
class Opencode:
    """How to invoke opencode, read once from the environment."""

    model: str = DEFAULT_MODEL
    # Provider-specific reasoning effort passed via `opencode run --variant`
    # (e.g. high / max / minimal). Blank disables the flag.
    variant: str = "high"
    # Plan first (read-only plan agent) then build, unless disabled.
    plan_first: bool = True
    # Hard ceiling, in seconds, on a single opencode pass. opencode has no
    # reliable stuck-detection for a silently stalled stream, so this is what
    # actually frees a CI runner when a pass hangs. 0 disables.
    timeout_s: int = 1800

    @classmethod
    def from_env(cls) -> Opencode:
        return cls(
            model=env("OPENCODE_MODEL", DEFAULT_MODEL),
            variant=env("OPENCODE_VARIANT", "high"),
            plan_first=env_bool("OPENCODE_PLAN", True),
            timeout_s=env_int("OPENCODE_TIMEOUT", 1800),
        )

    def run(
        self, prompt: str, *, agent: str | None = None, continue_session: bool = False
    ) -> None:
        opencode_env = {**os.environ, "OPENCODE_CONFIG": _config_path()}
        cmd = ["opencode", "run", "--model", self.model]
        if self.variant:
            cmd += ["--variant", self.variant]
        if agent:
            cmd += ["--agent", agent]
        if continue_session:
            cmd += ["--continue"]
        cmd.append(prompt)
        log(
            f"Running opencode (agent={agent or 'build'}, "
            f"variant={self.variant or 'default'}, prompt={len(prompt)} chars)…"
        )
        try:
            run(cmd, env=opencode_env, timeout=self.timeout_s or None)
        except subprocess.TimeoutExpired:
            sys.exit(
                f"opencode (agent={agent or 'build'}) exceeded its "
                f"{self.timeout_s}s timeout and was killed — the pass stalled. "
                "Raise OPENCODE_TIMEOUT if this was a legitimately long run."
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
        session (e.g. "Now execute the plan you just produced.").
        """
        if self.plan_first:
            self.run(context + "\n\n" + plan_instructions, agent="plan")
            self.run(
                build_lead_in + "\n" + build_instructions,
                agent="build",
                continue_session=True,
            )
        else:
            self.run(context + "\n\n" + build_instructions, agent="build")

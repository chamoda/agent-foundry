"""Pluggable harness protocol for coding agents.

A *harness* is the coding-agent driver that turns prompts into edits.  The
default is ``Opencode`` (opencode), but users can switch to ``ClaudeCode``
(or any future harness) via the ``HARNESS`` environment variable.

Usage::

    from foundry_core.harness import get_harness
    harness = get_harness()
    harness.plan_then_build(context, build_instructions, ...)
"""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable

from foundry_core.config import env


@runtime_checkable
class Harness(Protocol):
    """Minimal interface every coding-agent driver must satisfy."""

    def run(
        self, prompt: str, *, agent: str | None = None, continue_session: bool = False
    ) -> None: ...

    def plan_then_build(
        self,
        context: str,
        build_instructions: str,
        *,
        plan_instructions: str,
        build_lead_in: str,
    ) -> None: ...


_REGISTRY: dict[str, str] = {
    "opencode": "foundry_core.opencode.Opencode",
    "claude_code": "foundry_core.claude_code.ClaudeCode",
}


def get_harness() -> Harness:
    """Instantiate the harness selected by the ``HARNESS`` env var.

    Falls back to ``"opencode"`` when unset or unrecognized.
    """
    name = env("HARNESS", "opencode").strip().lower()
    path = _REGISTRY.get(name)
    if path is None:
        sys.exit(
            f"Unknown harness {name!r}. "
            f"Supported: {', '.join(sorted(_REGISTRY))}"
        )
    module_path, cls_name = path.rsplit(".", 1)
    # Lazy import so agents only pay for the harness they actually use.
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, cls_name)
    factory = getattr(cls, "from_env", None)
    if factory is None:
        sys.exit(f"Harness {cls_name!r} missing from_env() classmethod.")
    return factory()

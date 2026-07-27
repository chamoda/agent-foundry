"""GitHub Actions output helpers."""

from __future__ import annotations

import os

from foundry_core.shell import log


def set_output(name: str, value: str) -> None:
    """Write a key-value pair to ``$GITHUB_OUTPUT`` for downstream steps.

    When not running inside GitHub Actions (``GITHUB_OUTPUT`` unset), this is
    a no-op so local testing is unaffected.
    """
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")
    log(f"Output: {name}={value}")

"""Logging and subprocess helpers shared by all agents."""

from __future__ import annotations

import subprocess


def log(msg: str) -> None:
    print(f"==> {msg}", flush=True)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, check=True, **kwargs)


def working_tree_dirty() -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    return bool(out.strip())

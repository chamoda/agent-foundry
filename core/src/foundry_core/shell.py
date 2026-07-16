"""Logging and subprocess helpers shared by all agents."""

from __future__ import annotations

import os
import signal
import subprocess


def log(msg: str) -> None:
    print(f"==> {msg}", flush=True)


def run(
    cmd: list[str], *, timeout: int | None = None, **kwargs
) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    if timeout is None:
        return subprocess.run(cmd, check=True, **kwargs)
    # With a timeout we run the child in its own process group so a hang takes
    # down the whole tree (e.g. opencode *and* anything it spawned), not just
    # the direct child that subprocess.run's own timeout would reach.
    with subprocess.Popen(cmd, start_new_session=True, **kwargs) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            raise
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout=stdout, stderr=stderr)


def working_tree_dirty() -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    return bool(out.strip())

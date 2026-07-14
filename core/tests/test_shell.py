import subprocess

import pytest

from foundry_core.shell import run


def test_run_with_timeout_captures_stdout():
    result = run(["echo", "hello"], timeout=5, capture_output=True)
    assert result.stdout == b"hello\n"
    assert result.returncode == 0


def test_run_with_timeout_captures_stderr():
    result = run(
        ["sh", "-c", "echo err >&2"], timeout=5, capture_output=True
    )
    assert result.stderr == b"err\n"
    assert result.returncode == 0


def test_run_with_timeout_raises_on_nonzero_exit():
    with pytest.raises(subprocess.CalledProcessError):
        run(["false"], timeout=5)


def test_run_with_timeout_raises_on_timeout():
    with pytest.raises(subprocess.TimeoutExpired):
        run(["sleep", "10"], timeout=1)


def test_run_without_timeout_works():
    result = run(["echo", "hi"])
    assert result.returncode == 0

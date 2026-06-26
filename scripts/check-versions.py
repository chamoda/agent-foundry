"""Verify that all workspace packages declare the same version.

Reads ``version`` from each package's ``pyproject.toml`` and
``__version__`` from each ``src/<pkg>/__init__.py``, then asserts
they are all identical.  Exits non-zero with a clear message on
mismatch.

Usage::

    python scripts/check-versions.py          # from repo root
    python scripts/check-versions.py --quiet   # exit code only
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PACKAGES: dict[str, tuple[Path, str]] = {
    "core":       (REPO_ROOT / "core" / "pyproject.toml",       "foundry_core"),
    "nightwatch": (REPO_ROOT / "nightwatch" / "pyproject.toml", "nightwatch"),
    "daydream":   (REPO_ROOT / "daydream" / "pyproject.toml",   "daydream"),
    "lucid":      (REPO_ROOT / "lucid" / "pyproject.toml",      "lucid"),
}

_INIT_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def pyproject_version(path: Path) -> str:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def init_version(dir_name: str, python_pkg: str) -> str:
    init_path = REPO_ROOT / dir_name / "src" / python_pkg / "__init__.py"
    text = init_path.read_text()
    m = _INIT_RE.search(text)
    if m is None:
        raise SystemExit(f"ERROR: {init_path} has no __version__ line")
    return m.group(1)


def main() -> int:
    quiet = "--quiet" in sys.argv
    versions: dict[str, str] = {}

    for dir_name, (toml_path, python_pkg) in PACKAGES.items():
        versions[f"{dir_name}/pyproject.toml"] = pyproject_version(toml_path)
        versions[f"{python_pkg}/__init__.py"] = init_version(dir_name, python_pkg)

    unique = set(versions.values())

    if len(unique) == 1:
        if not quiet:
            print(f"OK: all packages at version {unique.pop()}")
        return 0

    target = max(unique)
    print(f"ERROR: version drift detected — expected all {target}\n")
    for label, ver in versions.items():
        status = "" if ver == target else " <-- MISMATCH"
        print(f"  {label}: {ver}{status}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

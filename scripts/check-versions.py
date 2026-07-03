#!/usr/bin/env python3
"""Verify that all workspace packages declare the same version.

Exits 0 if every ``pyproject.toml`` ``version`` field and every
``__init__.py`` ``__version__`` string are identical.  Exits 1 with a
diagnostic message on mismatch.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PACKAGES: dict[str, tuple[Path, Path]] = {
    "foundry-core":    (REPO_ROOT / "core"       / "pyproject.toml",   REPO_ROOT / "core"       / "src" / "foundry_core" / "__init__.py"),
    "nightwatch":      (REPO_ROOT / "nightwatch" / "pyproject.toml",   REPO_ROOT / "nightwatch" / "src" / "nightwatch"   / "__init__.py"),
    "daydream":        (REPO_ROOT / "daydream"   / "pyproject.toml",   REPO_ROOT / "daydream"   / "src" / "daydream"     / "__init__.py"),
    "lucid":           (REPO_ROOT / "lucid"      / "pyproject.toml",   REPO_ROOT / "lucid"      / "src" / "lucid"        / "__init__.py"),
    "warden":          (REPO_ROOT / "warden"     / "pyproject.toml",   REPO_ROOT / "warden"     / "src" / "warden"       / "__init__.py"),
}

_PYPROJECT_RE = re.compile(r"^version\s*=\s*\"([^\"]+)\"", re.MULTILINE)
_INIT_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


def _read_version(path: Path, pattern: re.Pattern[str]) -> str:  # noqa: UP043
    text = path.read_text()
    m = pattern.search(text)
    if not m:
        sys.exit(f"ERROR: could not find version in {path}")
    return m.group(1)


def main() -> None:
    errors: list[str] = []
    versions: dict[str, str] = {}

    for name, (pyproject, init_path) in PACKAGES.items():
        pyproject_ver = _read_version(pyproject, _PYPROJECT_RE)
        init_ver = _read_version(init_path, _INIT_RE)
        versions[name] = pyproject_ver

        if pyproject_ver != init_ver:
            errors.append(
                f"  {name}: pyproject.toml={pyproject_ver}, "
                f"__init__.py={init_ver}"
            )

    unique = set(versions.values())

    if len(unique) != 1:
        errors.append(
            "  packages declare different versions: "
            + ", ".join(f"{name}={ver}" for name, ver in sorted(versions.items()))
        )

    if errors:
        print("Version mismatch detected:\n")
        for e in errors:
            print(e)
        sys.exit(1)

    version = unique.pop()
    print(f"All packages at {version} — OK")


if __name__ == "__main__":
    main()

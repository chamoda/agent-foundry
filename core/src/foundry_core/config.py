"""Environment-variable configuration helpers.

Agents are configured exclusively through env vars set by their action.yml,
so these are the only configuration primitives the agents need.
"""

from __future__ import annotations

import os
import sys


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Missing required env var: {name}")
    return value or ""


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.lower() not in ("false", "0", "no")


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default

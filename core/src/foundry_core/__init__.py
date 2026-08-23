"""Shared core for agent-foundry agents.

Everything the individual agents have in common lives here: reading
configuration from the environment, logging/subprocess helpers, the opencode
driver, and small GitHub utilities.
"""

from foundry_core.config import env, env_bool, env_float, env_int
from foundry_core.gh import ensure_label, references_issue
from foundry_core.opencode import Opencode
from foundry_core.shell import log, run, working_tree_dirty
from foundry_core.summary import RunResult, write_summary

__version__ = "1.2.0"

__all__ = [
    "Opencode",
    "RunResult",
    "ensure_label",
    "env",
    "env_bool",
    "env_float",
    "env_int",
    "log",
    "references_issue",
    "run",
    "working_tree_dirty",
    "write_summary",
]

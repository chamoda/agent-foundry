"""Shared core for agent-foundry agents.

Everything the individual agents have in common lives here: reading
configuration from the environment, logging/subprocess helpers, the harness
protocol and built-in harness implementations, and small GitHub utilities.
"""

from foundry_core.config import env, env_bool, env_float, env_int
from foundry_core.gh import ensure_label, references_issue
from foundry_core.harness import Harness, get_harness
from foundry_core.opencode import Opencode
from foundry_core.shell import log, run, working_tree_dirty

__version__ = "1.1.2"

__all__ = [
    "Harness",
    "Opencode",
    "ensure_label",
    "env",
    "env_bool",
    "env_float",
    "env_int",
    "get_harness",
    "log",
    "references_issue",
    "run",
    "working_tree_dirty",
]

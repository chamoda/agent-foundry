"""Exception hierarchy for agent-foundry.

Libraries raise; applications (agent ``main()`` functions) handle.
"""

from __future__ import annotations


class FoundryError(Exception):
    """Base class for all agent-foundry errors."""


class ConfigError(FoundryError):
    """Bad or missing environment variables / settings."""


class AgentError(FoundryError):
    """Runtime failures: timeout, missing artifact, etc."""

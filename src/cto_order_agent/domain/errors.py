"""Domain-level failures. Each maps to a named validation rule."""

from __future__ import annotations


class AgentError(Exception):
    """Base class for expected, user-facing failures."""


class InvariantError(AgentError):
    """A model invariant was violated."""


class UngroundedFactError(AgentError):
    """A Fact was constructed without a retrievable source record."""


class FixtureIntegrityError(AgentError):
    """The synthetic corpus is internally inconsistent."""


class ValidationFailure(AgentError):
    """Narrative validation failed: a claim is not supported by the evidence bundle."""

    def __init__(self, ungrounded: list[str]) -> None:
        self.ungrounded = ungrounded
        super().__init__(f"ungrounded tokens: {', '.join(ungrounded)}")


class ToolFailure(AgentError):
    """A data source call failed."""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(f"{code}: {message}")


__all__ = [
    "AgentError",
    "FixtureIntegrityError",
    "InvariantError",
    "ToolFailure",
    "UngroundedFactError",
    "ValidationFailure",
]

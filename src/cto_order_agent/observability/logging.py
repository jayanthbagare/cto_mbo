"""Structured logging with a redaction processor.

Redaction runs as a processor so a missed field cannot leak through a forgotten
`extra=` argument.
"""

from __future__ import annotations

import re
from typing import Any, cast

import structlog

SENSITIVE = re.compile(r"(secret|token|password|authorization|api[_-]?key)", re.IGNORECASE)
MASK = "***"


def redact(value: Any) -> Any:
    """Recursively mask sensitive keys and inline token values."""
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            if SENSITIVE.search(str(key)) and item:
                result[key] = MASK
            else:
                result[key] = redact(item)
        return cast(dict[str, Any], result)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return re.sub(r"\b(gh[pousr]_[A-Za-z0-9]{10,}|Bearer\s+\S+)", MASK, value)
    return value


def _redaction_processor(logger: Any, method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], redact(event_dict))


def configure_logging(level: str = "INFO") -> None:
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redaction_processor,
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), level.upper(), 20)
        ),
        cache_logger_on_first_use=True,
    )


__all__ = ["MASK", "SENSITIVE", "configure_logging", "redact"]

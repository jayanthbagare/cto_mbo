"""OpenTelemetry spans, optional at runtime."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Emit a span when OpenTelemetry is installed; otherwise a no-op."""
    try:
        from opentelemetry import trace
    except Exception:  # noqa: BLE001 - tracing is never load-bearing
        yield
        return

    tracer = trace.get_tracer("cto_order_agent")
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, str(value))
        yield


__all__ = ["span"]

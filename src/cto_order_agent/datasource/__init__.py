"""Data access boundary. The only place that knows whether data is mock or live."""

from .protocol import SOURCE_SYNTHETIC, DataSource, envelope

__all__ = ["SOURCE_SYNTHETIC", "DataSource", "envelope"]

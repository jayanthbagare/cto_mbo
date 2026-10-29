"""Fixture-backed data source (synthetic corpus)."""

from .adapter import MockDataSource, load_dataset

__all__ = ["MockDataSource", "load_dataset"]

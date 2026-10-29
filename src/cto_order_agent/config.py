"""Settings. Secrets have no defaults and are never logged."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime

DEFAULT_CLOCK = "2026-01-15T08:00:00Z"

_TERMINAL = datetime(1, 1, 1, tzinfo=UTC)


def parse_clock(raw: str | None) -> datetime:
    """Parse an ISO instant, defaulting to the frozen evaluation clock."""
    if not raw:
        raw = DEFAULT_CLOCK
    raw = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class Settings:
    data_source: str = "mock"
    llm_mode: str = "recorded"
    ai_core_base_url: str = ""
    ai_core_client_id: str = ""
    ai_core_client_secret: str = field(default="", repr=False)
    ai_core_model: str = "gpt-4o"
    process_clock: datetime = field(default_factory=lambda: parse_clock(None))
    fixtures_dir: str = "fixtures/scenarios"
    portfolio_window_days: int = 365
    max_tasks: int = 1000
    task_ttl_seconds: int = 1800

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        return cls(
            data_source=e.get("DATA_SOURCE", "mock").strip().lower(),
            llm_mode=e.get("LLM_MODE", "recorded").strip().lower(),
            ai_core_base_url=e.get("AI_CORE_BASE_URL", ""),
            ai_core_client_id=e.get("AI_CORE_CLIENT_ID", ""),
            ai_core_client_secret=e.get("AI_CORE_CLIENT_SECRET", ""),
            ai_core_model=e.get("AI_CORE_MODEL", "gpt-4o"),
            process_clock=parse_clock(e.get("PROCESS_CLOCK")),
            fixtures_dir=e.get("FIXTURES_DIR", "fixtures/scenarios"),
            portfolio_window_days=int(e.get("PORTFOLIO_WINDOW_DAYS", "365")),
        )

    def redacted(self) -> dict[str, object]:
        """Safe representation for logs and health endpoints."""
        return {
            "data_source": self.data_source,
            "llm_mode": self.llm_mode,
            "ai_core_base_url": self.ai_core_base_url,
            "ai_core_client_id": self.ai_core_client_id,
            "ai_core_client_secret": "***" if self.ai_core_client_secret else "",
            "process_clock": self.process_clock.isoformat(),
            "fixtures_dir": self.fixtures_dir,
        }


__all__ = ["DEFAULT_CLOCK", "Settings", "parse_clock", "_TERMINAL"]

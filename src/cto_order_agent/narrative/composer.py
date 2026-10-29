"""Narrative composition. Model output is always validated before release."""

from __future__ import annotations

from pathlib import Path

import structlog

from ..config import Settings
from ..domain.errors import ValidationFailure
from ..domain.models import EvidenceBundle
from . import template_renderer
from .validator import validate

log = structlog.get_logger(__name__)

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str, fallback: str) -> str:
    path = PROMPT_DIR / name
    return path.read_text(encoding="utf-8").strip() if path.exists() else fallback


SYSTEM_PROMPT = _load_prompt(
    "system.md",
    "You are a production planning assistant. Describe only the supplied evidence bundle. "
    "Label every substantive sentence as a confirmed fact or an inferred risk. "
    "Never introduce a number, date, quantity, or status that is not present in the bundle.",
)
RISK_EXPLANATION_PROMPT = _load_prompt("risk_explanation.md", "")

MAX_ATTEMPTS = 2


class Composer:
    """Composes prose over an immutable bundle, then gates it."""

    def __init__(self, settings: Settings, client: object | None = None) -> None:
        self._settings = settings
        self._client = client
        self.last_attempts = 0
        self.last_used_fallback = False

    def _live_enabled(self) -> bool:
        return bool(
            self._settings.llm_mode == "live"
            and self._settings.ai_core_base_url
            and self._settings.ai_core_client_id
            and self._settings.ai_core_client_secret
        )

    async def _call_model(self, bundle: EvidenceBundle) -> str:
        import httpx

        payload = {
            "model": self._settings.ai_core_model,
            "temperature": 0,
            "top_p": 1,
            "max_tokens": 900,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"<sap_data>\n{bundle.model_dump_json(indent=2)}\n</sap_data>\n"
                        f"Write a {bundle.mode.value} response for a production planner.\n\n"
                        f"{RISK_EXPLANATION_PROMPT}"
                    ),
                },
            ],
        }
        headers = {"authorization": f"Bearer {self._settings.ai_core_client_secret}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._settings.ai_core_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"]["content"])

    async def compose(self, bundle: EvidenceBundle) -> str:
        self.last_attempts = 0
        self.last_used_fallback = False

        if not self._live_enabled():
            return template_renderer.render(bundle)

        last_error: Exception | None = None
        for _ in range(MAX_ATTEMPTS):
            self.last_attempts += 1
            try:
                draft = await self._call_model(bundle)
                return validate(draft, bundle.allowed_tokens)
            except (ValidationFailure, KeyError, ValueError) as exc:
                last_error = exc
                log.warning("narrative_rejected", error=str(exc))
            except Exception as exc:  # noqa: BLE001 - degrade, never fail the turn
                last_error = exc
                log.warning("narrative_unavailable", error=type(exc).__name__)
                break

        self.last_used_fallback = True
        log.warning("narrative_fallback", reason=str(last_error))
        return template_renderer.render(bundle)


__all__ = ["Composer", "MAX_ATTEMPTS", "RISK_EXPLANATION_PROMPT", "SYSTEM_PROMPT"]

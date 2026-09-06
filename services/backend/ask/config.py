"""LLM provider configuration for the contextual Ask endpoint.

Reads OpenAI-compatible provider settings from the environment so the same
implementation can target any compatible inference server (OpenRouter today,
vLLM / llama.cpp later). Keys are never read into source, fixtures, or logs.

If no key is configured, the Ask endpoint reports service-unavailable and the
rest of the application keeps functioning.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMSettings:
    base_url: str | None
    api_key: str | None
    model: str | None
    timeout_seconds: float = 30.0
    rate_limit: str = "10/minute"

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    @property
    def provider_identifier(self) -> str:
        """Safe identifier for logging — never includes the API key."""
        return self.model or "unconfigured"


def load_llm_settings() -> LLMSettings:
    return LLMSettings(
        base_url=os.environ.get("LLM_BASE_URL"),
        api_key=os.environ.get("LLM_API_KEY"),
        model=os.environ.get("LLM_MODEL"),
        timeout_seconds=float(os.environ.get("ASK_LLM_TIMEOUT_SECONDS", "30")),
        rate_limit=os.environ.get("ASK_RATE_LIMIT", "10/minute"),
    )

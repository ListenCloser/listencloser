"""LLM provider seam for the grounded contextual Ask endpoint.

A small `LLMProvider` protocol with two implementations:

- `FakeLLMProvider`  — deterministic responses for unit tests (never calls a
  network endpoint).
- `OpenAICompatibleLLMProvider` — talks to any OpenAI-compatible
  `/chat/completions` server (OpenRouter today; vLLM / llama.cpp later). The
  base URL, key, and model all come from environment configuration.

All providers must emit *structured* output validated by Pydantic after
generation. The provider never returns free-form prose.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol, TypeVar, runtime_checkable

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("ask.providers")

T = TypeVar("T", bound=BaseModel)


class AskProviderError(Exception):
    """Base class for provider failures surfaced as sanitized API errors."""


class AskProviderTimeoutError(AskProviderError):
    """The provider call exceeded its finite timeout."""


class AskProviderUnavailableError(AskProviderError):
    """The provider returned a transient 4xx/5xx failure."""


class AskProviderConfigurationError(AskProviderError):
    """No usable provider configuration (missing key/base URL/model)."""


class AskModelOutputError(AskProviderError):
    """The provider output did not parse/validate against the response model."""


@runtime_checkable
class LLMProvider(Protocol):
    """Generate a single structured completion.

    Implementations must return an instance of `response_model` (Pydantic
    validation is performed regardless of provider-side structured-output
    support). Raises `AskProviderError` subclasses on failure.
    """

    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T: ...


def _parse_json_object(content: str) -> dict:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AskModelOutputError("provider returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise AskModelOutputError("provider returned a non-object value")
    return parsed


class FakeLLMProvider:
    """Deterministic provider for unit tests.

    `responses` is a queue of JSON objects (or Pydantic-model instances)
    consumed in order. When exhausted, the last response is reused. Setting
    `error` makes every call raise the given `AskProviderError` subclass.

    Every call records its prompts so tests can assert the grounding payload
    reached the provider intact.
    """

    def __init__(
        self,
        responses: list[dict | BaseModel] | None = None,
        error: AskProviderError | None = None,
        *,
        model: str = "fake-ask-model",
    ) -> None:
        self._responses = list(responses or [])
        self._error = error
        self.model = model
        self.calls: list[tuple[str, str]] = []

    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        self.calls.append((system_prompt, user_prompt))
        if self._error is not None:
            raise self._error
        if not self._responses:
            raise AskModelOutputError("fake provider has no responses configured")
        payload = self._responses[0]
        if len(self._responses) > 1:
            self._responses.pop(0)
        if isinstance(payload, response_model):
            return payload
        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise AskModelOutputError("fake provider payload did not validate") from exc

    @property
    def last_system_prompt(self) -> str | None:
        return self.calls[-1][0] if self.calls else None

    @property
    def last_user_prompt(self) -> str | None:
        return self.calls[-1][1] if self.calls else None


class OpenAICompatibleLLMProvider:
    """Call an OpenAI-compatible `/chat/completions` endpoint.

    Generic on purpose: only the env-provided base URL, key, and model differ
    between providers. No provider-specific model names are hard-coded.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self._timeout_seconds = timeout_seconds
        self._client = client
        self._owns_client = client is None
        if self._owns_client:
            self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        endpoint = f"{self._base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = await self._client.post(endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AskProviderTimeoutError("provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise AskProviderUnavailableError("provider request failed") from exc

        if response.status_code >= 400:
            raise AskProviderUnavailableError(
                f"provider returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AskModelOutputError("provider response was not a chat completion") from exc

        parsed = _parse_json_object(content)
        try:
            return response_model.model_validate(parsed)
        except ValidationError as exc:
            logger.warning(
                "ask_model_output_invalid",
                extra={
                    "model": self.model,
                    "error": str(exc.errors()[:3]),
                },
            )
            raise AskModelOutputError(
                "provider output did not match the AskResponse schema"
            ) from exc

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()


def build_provider(settings, *, client: httpx.AsyncClient | None = None) -> LLMProvider | None:
    """Construct the production provider from config, or None when unconfigured."""
    if not settings.configured:
        return None
    return OpenAICompatibleLLMProvider(
        base_url=settings.base_url,  # type: ignore[arg-type]
        api_key=settings.api_key,  # type: ignore[arg-type]
        model=settings.model,  # type: ignore[arg-type]
        timeout_seconds=settings.timeout_seconds,
        client=client,
    )
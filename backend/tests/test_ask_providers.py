"""LLM provider seam tests — deterministic, no external network."""

from __future__ import annotations

import httpx
import pytest

from ask.config import LLMSettings
from ask.contracts import AskResponse
from ask.providers import (
    AskModelOutputError,
    AskProviderTimeoutError,
    AskProviderUnavailableError,
    FakeLLMProvider,
    OpenAICompatibleLLMProvider,
    build_provider,
)


async def test_fake_provider_returns_configured_response():
    provider = FakeLLMProvider(
        responses=[
            {"answer": "An answer.", "references": [], "suggestedActions": []}
        ]
    )
    result = await provider.complete_structured(
        system_prompt="system", user_prompt="user", response_model=AskResponse
    )
    assert isinstance(result, AskResponse)
    assert result.answer == "An answer."


async def test_fake_provider_records_prompts_for_grounding_assertions():
    provider = FakeLLMProvider(responses=[{"answer": "x", "references": []}])
    await provider.complete_structured(
        system_prompt="SYSTEM", user_prompt="USER", response_model=AskResponse
    )
    assert provider.calls == [("SYSTEM", "USER")]
    assert provider.last_system_prompt == "SYSTEM"
    assert provider.last_user_prompt == "USER"


async def test_fake_provider_rejects_invalid_payload():
    provider = FakeLLMProvider(responses=[{"unexpected": True}])
    with pytest.raises(AskModelOutputError):
        await provider.complete_structured(
            system_prompt="s", user_prompt="u", response_model=AskResponse
        )


async def test_fake_provider_propagates_configured_error():
    provider = FakeLLMProvider(error=AskProviderTimeoutError("timed out"))
    with pytest.raises(AskProviderTimeoutError):
        await provider.complete_structured(
            system_prompt="s", user_prompt="u", response_model=AskResponse
        )


def test_build_provider_returns_none_when_unconfigured():
    settings = LLMSettings(base_url=None, api_key=None, model=None)
    assert build_provider(settings) is None


def test_build_provider_returns_openai_compatible_when_configured():
    settings = LLMSettings(
        base_url="https://example.com/v1",
        api_key="secret",
        model="model-x",
    )
    provider = build_provider(settings)
    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider.model == "model-x"


def _mock_transport(response: httpx.Response | None = None, error: Exception | None = None):
    async def handler(request: httpx.Request) -> httpx.Response:
        if error is not None:
            raise error
        return response or httpx.Response(200, json={})

    return httpx.MockTransport(handler)


async def test_openai_compatible_parses_valid_structured_output():
    transport = _mock_transport(
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"answer": "Hi", "references": [], "suggestedActions": []}'
                        }
                    }
                ]
            },
        )
    )
    provider = OpenAICompatibleLLMProvider(
        base_url="https://example.com/v1",
        api_key="secret",
        model="model-x",
        client=httpx.AsyncClient(transport=transport),
    )

    result = await provider.complete_structured(
        system_prompt="s", user_prompt="u", response_model=AskResponse
    )
    assert result.answer == "Hi"


async def test_openai_compatible_rejects_malformed_json_output():
    transport = _mock_transport(
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )
    )
    provider = OpenAICompatibleLLMProvider(
        base_url="https://example.com/v1",
        api_key="secret",
        model="model-x",
        client=httpx.AsyncClient(transport=transport),
    )
    with pytest.raises(AskModelOutputError):
        await provider.complete_structured(
            system_prompt="s", user_prompt="u", response_model=AskResponse
        )


async def test_openai_compatible_rejects_schema_invalid_output():
    transport = _mock_transport(
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"nope": 1}'}}]},
        )
    )
    provider = OpenAICompatibleLLMProvider(
        base_url="https://example.com/v1",
        api_key="secret",
        model="model-x",
        client=httpx.AsyncClient(transport=transport),
    )
    with pytest.raises(AskModelOutputError):
        await provider.complete_structured(
            system_prompt="s", user_prompt="u", response_model=AskResponse
        )


async def test_openai_compatible_surfaces_5xx_as_unavailable():
    transport = _mock_transport(httpx.Response(500, json={"error": "boom"}))
    provider = OpenAICompatibleLLMProvider(
        base_url="https://example.com/v1",
        api_key="secret",
        model="model-x",
        client=httpx.AsyncClient(transport=transport),
    )
    with pytest.raises(AskProviderUnavailableError):
        await provider.complete_structured(
            system_prompt="s", user_prompt="u", response_model=AskResponse
        )


async def test_openai_compatible_surfaces_4xx_as_unavailable():
    transport = _mock_transport(httpx.Response(429, json={"error": "rate limited"}))
    provider = OpenAICompatibleLLMProvider(
        base_url="https://example.com/v1",
        api_key="secret",
        model="model-x",
        client=httpx.AsyncClient(transport=transport),
    )
    with pytest.raises(AskProviderUnavailableError):
        await provider.complete_structured(
            system_prompt="s", user_prompt="u", response_model=AskResponse
        )


async def test_openai_compatible_surfaces_timeout():
    transport = _mock_transport(error=httpx.ReadTimeout("timed out"))
    provider = OpenAICompatibleLLMProvider(
        base_url="https://example.com/v1",
        api_key="secret",
        model="model-x",
        timeout_seconds=1.0,
        client=httpx.AsyncClient(transport=transport),
    )
    with pytest.raises(AskProviderTimeoutError):
        await provider.complete_structured(
            system_prompt="s", user_prompt="u", response_model=AskResponse
        )


def test_openai_compatible_missing_configuration_error_is_not_raised_by_provider():
    """Missing configuration is an endpoint concern (503), not a provider one."""
    settings = LLMSettings(base_url=None, api_key=None, model=None)
    assert build_provider(settings) is None
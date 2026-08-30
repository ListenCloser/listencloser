"""Regression coverage for the Ask provider's per-request timeout."""

from __future__ import annotations

import httpx
import pytest

from ask.contracts import AskResponse
from ask.providers import OpenAICompatibleLLMProvider


@pytest.mark.asyncio
async def test_shared_client_uses_ask_specific_timeout() -> None:
    observed_timeout: dict[str, float] | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_timeout
        observed_timeout = request.extensions.get("timeout")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"answer":"ok","references":[],"suggestedActions":[]}'
                        }
                    }
                ]
            },
        )

    shared_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        timeout=120.0,
    )
    try:
        provider = OpenAICompatibleLLMProvider(
            base_url="https://example.com/v1",
            api_key="secret",
            model="model-x",
            timeout_seconds=7.5,
            client=shared_client,
        )
        result = await provider.complete_structured(
            system_prompt="s",
            user_prompt="u",
            response_model=AskResponse,
        )
    finally:
        await shared_client.aclose()

    assert result.answer == "ok"
    assert observed_timeout is not None
    assert observed_timeout["connect"] == pytest.approx(7.5)
    assert observed_timeout["read"] == pytest.approx(7.5)
    assert observed_timeout["write"] == pytest.approx(7.5)
    assert observed_timeout["pool"] == pytest.approx(7.5)

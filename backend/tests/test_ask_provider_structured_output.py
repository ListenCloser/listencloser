"""No-network coverage for the production Ask structured-output request."""

from __future__ import annotations

import asyncio
import json

import httpx

from ask.contracts import AskResponse
from ask.providers import OpenAICompatibleLLMProvider


def _assert_strict_object_contract(node) -> None:
    if isinstance(node, dict):
        assert "default" not in node
        assert "oneOf" not in node
        assert "discriminator" not in node
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
            properties = node.get("properties", {})
            assert set(node.get("required", [])) == set(properties)
        for value in node.values():
            _assert_strict_object_contract(value)
    elif isinstance(node, list):
        for value in node:
            _assert_strict_object_contract(value)


def test_openrouter_request_requires_strict_ask_response_schema() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "answer": "C major is supported by the supplied evidence.",
                                    "references": [],
                                    "suggestedActions": [],
                                }
                            )
                        }
                    }
                ]
            },
        )

    async def invoke() -> AskResponse:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAICompatibleLLMProvider(
                base_url="https://openrouter.ai/api/v1",
                api_key="test-key",
                model="openai/gpt-latest",
                client=client,
            )
            return await provider.complete_structured(
                system_prompt="Use only supplied evidence.",
                user_prompt="What tonal center is supported?",
                response_model=AskResponse,
            )

    response = asyncio.run(invoke())

    assert response.answer.startswith("C major")
    assert captured["provider"] == {"require_parameters": True}
    response_format = captured["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "AskResponse"
    assert response_format["json_schema"]["strict"] is True

    schema = response_format["json_schema"]["schema"]
    assert set(schema["required"]) == {"answer", "references", "suggestedActions"}
    _assert_strict_object_contract(schema)

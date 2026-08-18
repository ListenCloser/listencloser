"""Optional real-provider smoke test (opt-in, skipped by default).

Run with `ASK_REAL_PROVIDER=1` and a configured `LLM_BASE_URL` / `LLM_API_KEY`
/ `LLM_MODEL` to verify one inexpensive grounded question returns schema-valid
output against the live provider. Never runs in ordinary unit tests and never
exposes the API key.
"""

from __future__ import annotations

import os

import pytest

from ask.config import load_llm_settings
from ask.contracts import AskContext, AskInsight, AskInsightSpan, AskVisibleInsight
from ask.grounding import build_grounded_prompts
from ask.providers import build_provider

pytestmark = [
    pytest.mark.external_provider,
    pytest.mark.skipif(
        os.environ.get("ASK_REAL_PROVIDER") != "1",
        reason="ASK_REAL_PROVIDER is not set to 1",
    ),
]


@pytest.mark.asyncio
async def test_real_provider_returns_schema_valid_answer():
    settings = load_llm_settings()
    if not settings.configured:
        pytest.skip("LLM_BASE_URL / LLM_API_KEY / LLM_MODEL not configured")

    provider = build_provider(settings)
    assert provider is not None

    context = AskContext(
        workId="00000000-0000-0000-0000-000000000001",
        representationId="score",
        currentTime=2.0,
        playbackSourceId=None,
        selection=None,
        visibleInsights=[
            AskVisibleInsight(
                insight=AskInsight(
                    id="insight-key",
                    version_id="version-1",
                    kind="key",
                    claim="Key: C major",
                    span=AskInsightSpan(start_seconds=0.0, end_seconds=4.0),
                ),
                category="whole-work",
            )
        ],
    )
    system_prompt, user_prompt = build_grounded_prompts("What key is this piece in?", context)

    result = await provider.complete_structured(  # type: ignore[misc]
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=__import__("ask.contracts", fromlist=["AskResponse"]).AskResponse,
    )

    assert result.answer.strip()
    assert isinstance(result.references, list)
    if hasattr(provider, "aclose"):
        await provider.aclose()  # type: ignore[attr-defined]

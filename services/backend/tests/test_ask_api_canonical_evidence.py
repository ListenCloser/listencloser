"""Ask API integration tests for server-canonical evidence context."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from ask.contracts import AskContext, AskInsight, AskInsightSpan, AskVisibleInsight
from ask.providers import FakeLLMProvider
from auth_utils import verify_token
from main import app

AUTH_HEADER = {"Authorization": "Bearer fake-token"}
WORK_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def canonical_api(monkeypatch):
    app.dependency_overrides[verify_token] = lambda: SimpleNamespace(
        user=SimpleNamespace(id="owner-1")
    )

    class FakeWorkRepo:
        def __init__(self, client):
            self.client = client

        def get(self, work_id, owner_id):
            return SimpleNamespace(id=work_id) if str(work_id) == WORK_ID else None

    monkeypatch.setattr("ask.api.WorkRepo", FakeWorkRepo)
    monkeypatch.setattr("ask.api.get_supabase", lambda: SimpleNamespace())
    yield
    app.dependency_overrides.pop(verify_token, None)


def _body(insight_id: str):
    return {
        "question": "What happens here?",
        "context": {
            "workId": WORK_ID,
            "representationId": "piano_roll",
            "currentTime": 2.0,
            "selection": {
                "timeRange": {"start": 2.0, "end": 4.0, "domain": "performance"},
                "provenance": {
                    "origin": "piano_roll",
                    "timeExact": True,
                    "measureApproximate": False,
                },
            },
            "visibleInsights": [
                {
                    "insight": {
                        "id": insight_id,
                        "version_id": str(uuid4()),
                        "kind": "key",
                        "claim": "CLIENT FORGED CLAIM",
                        "span": {},
                        "entity_ids": [],
                    },
                    "category": "whole-work",
                }
            ],
        },
    }


def test_prompt_and_sanitizer_use_same_server_canonical_context(
    client,
    canonical_api,
    monkeypatch,
):
    insight_id = str(uuid4())
    canonical_version_id = str(uuid4())
    fake = FakeLLMProvider(
        responses=[
            {
                "answer": "The persisted evidence supports this description.",
                "references": [
                    {"type": "insight", "id": insight_id},
                    {"type": "insight", "id": "client-only-invented"},
                ],
            }
        ]
    )
    monkeypatch.setattr("ask.api.build_provider", lambda settings, client=None: fake)

    def canonicalize(sb, context: AskContext) -> AskContext:
        assert context.visibleInsights[0].insight.claim == "CLIENT FORGED CLAIM"
        canonical = AskVisibleInsight(
            insight=AskInsight(
                id=insight_id,
                version_id=canonical_version_id,
                kind="chord",
                claim="Persisted chord: G7",
                span=AskInsightSpan(start_seconds=2.25, end_seconds=3.75),
                entity_ids=[],
            ),
            category="selection",
        )
        return context.model_copy(update={"visibleInsights": [canonical]})

    monkeypatch.setattr("ask.api.load_canonical_ask_context", canonicalize)

    response = client.post("/api/v1/ask", json=_body(insight_id), headers=AUTH_HEADER)

    assert response.status_code == 200
    assert fake.last_user_prompt is not None
    assert "Persisted chord: G7" in fake.last_user_prompt
    assert "CLIENT FORGED CLAIM" not in fake.last_user_prompt
    # Version lineage is used server-side to authorize/canonicalize the Insight,
    # but is deliberately not exposed to the LLM evidence serializer.
    assert canonical_version_id not in fake.last_user_prompt
    assert '"category": "selection"' in fake.last_user_prompt
    assert response.json()["references"] == [{"type": "insight", "id": insight_id}]


def test_invalid_client_evidence_cannot_authorize_model_reference(
    client,
    canonical_api,
    monkeypatch,
):
    insight_id = str(uuid4())
    fake = FakeLLMProvider(
        responses=[
            {
                "answer": "There is no validated evidence for that claim.",
                "references": [{"type": "insight", "id": insight_id}],
            }
        ]
    )
    monkeypatch.setattr("ask.api.build_provider", lambda settings, client=None: fake)
    monkeypatch.setattr(
        "ask.api.load_canonical_ask_context",
        lambda sb, context: context.model_copy(update={"visibleInsights": []}),
    )

    response = client.post("/api/v1/ask", json=_body(insight_id), headers=AUTH_HEADER)

    assert response.status_code == 200
    assert fake.last_user_prompt is not None
    assert "CLIENT FORGED CLAIM" not in fake.last_user_prompt
    assert response.json()["references"] == []

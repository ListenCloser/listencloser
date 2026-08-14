"""FE/BE contract integration fixture — exactly what the frontend sends.

The payload below mirrors the request shape produced by
`lib/ask/client.ts` / `deriveAskContext` on the frontend (#226/#227). It must
validate against the backend contract and, with a FakeLLMProvider, produce a
JSON response the frontend can consume as its `AskResponse` type.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ask.providers import FakeLLMProvider
from auth_utils import verify_token
from main import app

AUTH_HEADER = {"Authorization": "Bearer fake-token"}

# The exact shape the frontend sends (see tests/lib/ask/client.test.ts).
FRONTEND_ASK_REQUEST = {
    "question": "What is happening harmonically here?",
    "context": {
        "workId": "00000000-0000-0000-0000-000000000001",
        "representationId": "piano_roll",
        "currentTime": 15.0,
        "playbackSourceId": "perf-source",
        "selection": {
            "timeRange": {"start": 31.0, "end": 38.0, "domain": "performance"},
            "noteIds": ["note-1", "note-2", "note-3"],
            "provenance": {
                "origin": "piano_roll",
                "timeExact": True,
                "measureApproximate": False,
            },
        },
        "visibleInsights": [
            {
                "insight": {
                    "id": "insight-selection",
                    "version_id": "version-1",
                    "kind": "chord",
                    "claim": "Chord: G7",
                    "span": {
                        "start_seconds": 32.0,
                        "end_seconds": 35.0,
                        "start_beat": None,
                        "end_beat": None,
                        "start_measure": None,
                        "end_measure": None,
                    },
                    "entity_ids": [],
                },
                "category": "selection",
            },
            {
                "insight": {
                    "id": "insight-key",
                    "version_id": "version-1",
                    "kind": "key",
                    "claim": "Key: C major",
                    "span": {
                        "start_seconds": None,
                        "end_seconds": None,
                        "start_beat": None,
                        "end_beat": None,
                        "start_measure": None,
                        "end_measure": None,
                    },
                    "entity_ids": [],
                },
                "category": "whole-work",
            },
        ],
    },
}


@pytest.fixture
def contract_env(monkeypatch):
    app.dependency_overrides[verify_token] = lambda: SimpleNamespace(
        user=SimpleNamespace(id="owner-1")
    )

    import domain.repositories as repo

    work = SimpleNamespace(id="00000000-0000-0000-0000-000000000001")

    class FakeWorkRepo:
        def __init__(self, client):
            self.client = client

        def get(self, work_id, owner_id):
            return work

    monkeypatch.setattr(repo, "WorkRepo", FakeWorkRepo)
    monkeypatch.setattr(repo, "get_supabase", lambda: SimpleNamespace())
    monkeypatch.setattr("ask.api.WorkRepo", FakeWorkRepo)
    monkeypatch.setattr("ask.api.get_supabase", lambda: SimpleNamespace())
    monkeypatch.setattr(
        "ask.api.build_provider",
        lambda settings: FakeLLMProvider(
            responses=[
                {
                    "answer": "G7 creates dominant tension that resolves to C major.",
                    "references": [
                        {"type": "insight", "id": "insight-selection"},
                        {"type": "notes", "ids": ["note-1", "note-2"]},
                        {"type": "time", "start": 31.0, "end": 35.0, "domain": "performance"},
                    ],
                    "suggestedActions": [
                        {"type": "show_representation", "representationId": "score"},
                    ],
                }
            ]
        ),
    )
    yield
    app.dependency_overrides.pop(verify_token, None)


def test_frontend_request_is_accepted_and_response_matches_frontend_type(
    client, contract_env
):
    response = client.post("/api/v1/ask", json=FRONTEND_ASK_REQUEST, headers=AUTH_HEADER)

    assert response.status_code == 200
    payload = response.json()

    # The response must be consumable as the frontend AskResponse type:
    #   { answer: string; references: AskReference[]; suggestedActions?: AskAction[] }
    assert isinstance(payload["answer"], str)
    assert isinstance(payload["references"], list)
    assert isinstance(payload["suggestedActions"], list)

    reference = payload["references"][0]
    assert reference["type"] == "insight"
    assert reference["id"] == "insight-selection"

    notes_reference = payload["references"][1]
    assert notes_reference["type"] == "notes"
    assert notes_reference["ids"] == ["note-1", "note-2"]

    time_reference = payload["references"][2]
    assert time_reference["type"] == "time"
    assert time_reference["domain"] == "performance"

    action = payload["suggestedActions"][0]
    assert action["type"] == "show_representation"
    assert action["representationId"] == "score"


def test_frontend_contract_request_validates_against_backend_models():
    from ask.contracts import AskRequest

    parsed = AskRequest.model_validate(FRONTEND_ASK_REQUEST)
    assert parsed.question == "What is happening harmonically here?"
    assert str(parsed.context.workId) == "00000000-0000-0000-0000-000000000001"
    assert parsed.context.selection is not None
    assert parsed.context.selection.noteIds == ["note-1", "note-2", "note-3"]
    assert parsed.context.visibleInsights[0].category == "selection"
    assert parsed.context.visibleInsights[1].category == "whole-work"
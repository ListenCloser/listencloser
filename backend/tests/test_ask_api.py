"""POST /api/v1/ask endpoint tests — deterministic, FakeLLMProvider, no network."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ask.providers import (
    AskModelOutputError,
    AskProviderTimeoutError,
    FakeLLMProvider,
)
from auth_utils import verify_token
from main import app

AUTH_HEADER = {"Authorization": "Bearer fake-token"}


def _fake_auth_user():
    return SimpleNamespace(user=SimpleNamespace(id="owner-1"))


@pytest.fixture
def override_auth():
    app.dependency_overrides[verify_token] = lambda: _fake_auth_user()
    yield
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def override_supabase(monkeypatch):
    """Point the endpoint at a fake Supabase with one owned work."""
    import domain.repositories as repo

    work = SimpleNamespace(id="00000000-0000-0000-0000-000000000001")

    class FakeWorkRepo:
        def __init__(self, client):
            self.client = client

        def get(self, work_id, owner_id):
            if str(work_id) == "00000000-0000-0000-0000-000000000001":
                return work
            return None

    monkeypatch.setattr(repo, "WorkRepo", FakeWorkRepo)
    monkeypatch.setattr(repo, "get_supabase", lambda: SimpleNamespace())
    monkeypatch.setattr("ask.api.WorkRepo", FakeWorkRepo)
    monkeypatch.setattr("ask.api.get_supabase", lambda: SimpleNamespace())


@pytest.fixture
def override_provider(monkeypatch):
    def _install(fake: FakeLLMProvider):
        monkeypatch.setattr("ask.api.build_provider", lambda settings: fake)

    return _install


def _ask_body(question: str = "What is happening harmonically here?"):
    return {
        "question": question,
        "context": {
            "workId": "00000000-0000-0000-0000-000000000001",
            "representationId": "score",
            "currentTime": 2.0,
            "playbackSourceId": "source-1",
            "selection": {
                "timeRange": {"start": 2.0, "end": 4.0, "domain": "performance"},
                "noteIds": ["note-1", "note-2"],
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
                            "start_seconds": 2.0,
                            "end_seconds": 4.0,
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


def _valid_response_payload() -> dict:
    return {
        "answer": "G7 creates dominant tension that resolves to C major.",
        "references": [
            {"type": "insight", "id": "insight-selection"},
            {"type": "time", "start": 1.0, "end": 3.0, "domain": "performance"},
        ],
        "suggestedActions": [
            {"type": "show_representation", "representationId": "score"},
            {"type": "seek", "seconds": 2.0, "domain": "performance"},
        ],
    }


def test_valid_grounded_question_returns_ask_response(
    client, override_auth, override_supabase, override_provider
):
    override_provider(FakeLLMProvider(responses=[_valid_response_payload()]))

    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("G7 creates dominant tension")
    assert {ref["type"] for ref in data["references"]} == {"insight", "time"}
    assert data["suggestedActions"][0]["type"] == "show_representation"


def test_no_selection_whole_work_context_accepted(
    client, override_auth, override_supabase, override_provider
):
    override_provider(
        FakeLLMProvider(responses=[{"answer": "Whole work summary.", "references": []}])
    )
    body = _ask_body()
    body["context"]["selection"] = None
    body["context"]["visibleInsights"] = [
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
        }
    ]

    response = client.post("/api/v1/ask", json=body, headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json()["answer"] == "Whole work summary."


def test_selection_specific_and_whole_work_evidence_remain_distinguishable(
    client, override_auth, override_supabase, override_provider
):
    fake = FakeLLMProvider(responses=[_valid_response_payload()])
    override_provider(fake)

    client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert fake.last_user_prompt is not None
    assert "insight-selection" in fake.last_user_prompt
    assert '"category": "selection"' in fake.last_user_prompt
    assert '"category": "whole-work"' in fake.last_user_prompt


def test_insufficient_evidence_answer_accepted(
    client, override_auth, override_supabase, override_provider
):
    override_provider(
        FakeLLMProvider(
            responses=[{"answer": "I don't have enough evidence.", "references": []}]
        )
    )
    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json()["answer"] == "I don't have enough evidence."


def test_malformed_model_output_rejected(
    client, override_auth, override_supabase, override_provider
):
    override_provider(FakeLLMProvider(error=AskModelOutputError("bad")))
    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 502
    assert "invalid response" in response.json()["detail"]


def test_invented_insight_reference_removed(
    client, override_auth, override_supabase, override_provider
):
    payload = _valid_response_payload()
    payload["references"] = [{"type": "insight", "id": "invented-id"}]
    override_provider(FakeLLMProvider(responses=[payload]))

    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json()["references"] == []


def test_invented_note_id_removed(
    client, override_auth, override_supabase, override_provider
):
    payload = _valid_response_payload()
    payload["references"] = [{"type": "notes", "ids": ["note-1", "ghost"]}]
    override_provider(FakeLLMProvider(responses=[payload]))

    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json()["references"] == []


def test_invalid_representation_action_removed(
    client, override_auth, override_supabase, override_provider
):
    payload = _valid_response_payload()
    payload["suggestedActions"] = [
        {"type": "show_representation", "representationId": "harmony"}
    ]
    override_provider(FakeLLMProvider(responses=[payload]))

    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json()["suggestedActions"] is None


def test_negative_time_reference_removed(
    client, override_auth, override_supabase, override_provider
):
    payload = _valid_response_payload()
    payload["references"] = [
        {"type": "time", "start": -1.0, "end": 3.0, "domain": "performance"}
    ]
    override_provider(FakeLLMProvider(responses=[payload]))

    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.json()["references"] == []


def test_reversed_time_range_removed(
    client, override_auth, override_supabase, override_provider
):
    payload = _valid_response_payload()
    payload["references"] = [
        {"type": "time", "start": 10.0, "end": 3.0, "domain": "performance"}
    ]
    override_provider(FakeLLMProvider(responses=[payload]))

    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.json()["references"] == []


def test_cross_domain_unsafe_action_removed(
    client, override_auth, override_supabase, override_provider
):
    payload = _valid_response_payload()
    payload["suggestedActions"] = [
        {"type": "seek", "seconds": 2.0, "domain": "notation"}
    ]
    override_provider(FakeLLMProvider(responses=[payload]))

    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json()["suggestedActions"] is None


def test_provider_timeout_returns_sanitized_error(
    client, override_auth, override_supabase, override_provider
):
    override_provider(FakeLLMProvider(error=AskProviderTimeoutError("timed out")))
    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 504


def test_missing_provider_configuration_returns_service_unavailable(
    client, override_auth, override_supabase, monkeypatch
):
    monkeypatch.setattr(
        "ask.api.build_provider", lambda settings: None
    )
    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_oversized_question_rejected(
    client, override_auth, override_supabase, override_provider
):
    override_provider(FakeLLMProvider(responses=[_valid_response_payload()]))
    response = client.post(
        "/api/v1/ask",
        json=_ask_body(question="x" * 5000),
        headers=AUTH_HEADER,
    )

    assert response.status_code == 422


def test_unauthorized_request_rejected(client):
    response = client.post("/api/v1/ask", json=_ask_body())
    assert response.status_code == 401


def test_work_not_owned_returns_403(client, override_auth, override_supabase, monkeypatch):
    monkeypatch.setattr(
        "ask.api.build_provider",
        lambda settings: FakeLLMProvider(responses=[_valid_response_payload()]),
    )

    class DenyWorkRepo:
        def __init__(self, client):
            self.client = client

        def get(self, work_id, owner_id):
            raise PermissionError("project not found or not owned by caller")

    monkeypatch.setattr("ask.api.WorkRepo", DenyWorkRepo)
    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 403


def test_missing_work_returns_404(client, override_auth, override_supabase, override_provider):
    override_provider(FakeLLMProvider(responses=[_valid_response_payload()]))
    body = _ask_body()
    body["context"]["workId"] = "00000000-0000-0000-0000-000000000099"
    response = client.post("/api/v1/ask", json=body, headers=AUTH_HEADER)

    assert response.status_code == 404


def test_fake_provider_receives_expected_grounded_evidence(
    client, override_auth, override_supabase, override_provider
):
    fake = FakeLLMProvider(responses=[_valid_response_payload()])
    override_provider(fake)

    response = client.post("/api/v1/ask", json=_ask_body(), headers=AUTH_HEADER)

    assert response.status_code == 200
    assert fake.last_system_prompt is not None
    assert "explaining supplied musical-analysis evidence" in fake.last_system_prompt
    assert fake.last_user_prompt is not None
    assert "Chord: G7" in fake.last_user_prompt
    assert "Key: C major" in fake.last_user_prompt
    assert '"work_id": "00000000-0000-0000-0000-000000000001"' in fake.last_user_prompt
    assert "note-1" in fake.last_user_prompt


def test_rate_limit_is_configurable_and_conservative(client, monkeypatch):
    monkeypatch.setenv("ASK_RATE_LIMIT", "1/minute")
    from ask.config import load_llm_settings

    assert load_llm_settings().rate_limit == "1/minute"
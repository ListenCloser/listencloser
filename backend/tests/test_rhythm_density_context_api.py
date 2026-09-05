from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import domain.relation_api as relation_api
from auth_utils import verify_token
from domain.models import Artifact, ArtifactKind, Insight, Version, Work
from domain.work_bundle_repository import WorkBundleSnapshot
from main import app

AUTH_HEADER = {"Authorization": "Bearer fake-token"}


@pytest.fixture
def override_auth():
    app.dependency_overrides[verify_token] = lambda: SimpleNamespace(
        user=SimpleNamespace(id="owner-1")
    )
    yield
    app.dependency_overrides.pop(verify_token, None)


def _window(start: float, end: float, density: float) -> dict:
    return {
        "start": start,
        "end": end,
        "density": density,
        "mode": "beat_relative",
        "unit": "events_per_beat",
        "coordinate_unit": "beats",
        "window_size": 2.0,
        "step_size": 1.0,
    }


def _windows() -> list[dict]:
    return [
        _window(0.0, 2.0, 1.0),
        _window(1.0, 3.0, 1.0),
        _window(2.0, 4.0, 2.0),
        _window(3.0, 5.0, 4.0),
        _window(4.0, 6.0, 5.0),
        _window(5.0, 7.0, 4.0),
        _window(6.0, 8.0, 2.0),
        _window(7.0, 9.0, 3.0),
        _window(8.0, 10.0, 1.0),
    ]


def _snapshot():
    work = Work(project_id=uuid4(), title="Context API test")
    artifact = Artifact(
        work_id=work.id,
        kind=ArtifactKind.midi_performance,
        mime_type="audio/midi",
    )
    version = Version(
        artifact_id=artifact.id,
        storage_key="analysis-input.mid",
        storage_bucket="artifacts",
        created_by="owner-1",
        label="Analysis MIDI",
    )
    return (
        WorkBundleSnapshot(
            work=work,
            artifacts=[artifact],
            versions_by_artifact={artifact.id: [version]},
            jobs=[],
        ),
        version,
    )


def _density_insight(version_id) -> Insight:
    windows = _windows()
    return Insight(
        version_id=version_id,
        kind="rhythm_density",
        claim="Note density profile",
        evidence={
            "windows": windows,
            "coverage": {
                "policy_version": "complete_series_v1",
                "total_generated_window_count": len(windows),
                "stored_window_count": len(windows),
                "start_seconds": windows[0]["start"],
                "end_seconds": windows[-1]["end"],
                "truncated": False,
            },
        },
        confidence=None,
        provenance={
            "method": "computed",
            "engine": {"engine": "beat_this", "engine_version": "1.1.0"},
        },
        created_at=datetime(2026, 9, 4, 20, tzinfo=UTC),
        created_by="owner-1",
    )


def _body(version_id, *, start=4.0, end=6.0):
    return {
        "density_owner_version_id": str(version_id),
        "subject_start_seconds": start,
        "subject_end_seconds": end,
        "subject_origin": "user_selected",
    }


def _install_snapshot(monkeypatch, snapshot):
    calls = []

    class FakeWorkBundleRepository:
        def __init__(self, client):
            self.client = client

        def load(self, work_id, owner_id):
            calls.append((work_id, owner_id))
            return snapshot

    monkeypatch.setattr(relation_api, "WorkBundleRepository", FakeWorkBundleRepository)
    return calls


def _install_insights(monkeypatch, insights):
    calls = []

    class FakeInsightRepo:
        def __init__(self, client):
            self.client = client

        def list_by_version(self, version_id, owner_id):
            calls.append((version_id, owner_id))
            if isinstance(insights, Exception):
                raise insights
            return list(insights)

    monkeypatch.setattr(relation_api, "InsightRepo", FakeInsightRepo)
    return calls


def test_supported_context_is_authorized_exact_version_and_serialized_without_raw_windows(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, version = _snapshot()
    density = _density_insight(version.id)
    work_calls = _install_snapshot(monkeypatch, snapshot)
    insight_calls = _install_insights(monkeypatch, [density])
    monkeypatch.setattr(relation_api, "get_supabase", lambda: SimpleNamespace())

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/rhythm-density-context",
        json=_body(version.id),
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "supported"
    assert payload["rhythm_density_insight_id"] == str(density.id)
    assert payload["reasons"] == []
    finding = payload["finding"]
    assert finding["kind"] == "rhythm_density_work_context"
    assert finding["subject_locator"]["source_artifact_version_id"] == str(version.id)
    assert finding["subject_locator"]["authority"] == "user_selected"
    assert finding["subject_origin"] == "user_selected"
    assert finding["selection_conditioned_on_rhythm_density"] is False
    assert finding["reference_population"]["kind"] == "work_excluding_subject"
    assert finding["support_refs"] == [
        {
            "type": "external",
            "namespace": "rhythm_density_insight",
            "id": f"{density.id}:rhythm_density",
        }
    ]
    assert '"windows"' not in response.text
    assert work_calls == [(snapshot.work.id, "owner-1")]
    assert insight_calls == [(version.id, "owner-1")]


def test_context_states_preserve_abstention_without_transport_errors(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, version = _snapshot()
    _install_snapshot(monkeypatch, snapshot)
    insight_calls = _install_insights(monkeypatch, [])
    monkeypatch.setattr(relation_api, "get_supabase", lambda: SimpleNamespace())

    unavailable = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/rhythm-density-context",
        json=_body(version.id),
        headers=AUTH_HEADER,
    )
    assert unavailable.status_code == 200
    assert unavailable.json()["status"] == "unavailable"
    assert unavailable.json()["finding"] is None

    density = _density_insight(version.id)
    insight_calls.clear()
    _install_insights(monkeypatch, [density])
    withheld = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/rhythm-density-context",
        json=_body(version.id, start=20.0, end=22.0),
        headers=AUTH_HEADER,
    )
    assert withheld.status_code == 200
    assert withheld.json()["status"] == "withheld"
    assert withheld.json()["finding"] is None

    _install_insights(monkeypatch, RuntimeError("private persistence detail"))
    failed = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/rhythm-density-context",
        json=_body(version.id),
        headers=AUTH_HEADER,
    )
    assert failed.status_code == 200
    assert failed.json() == {
        "status": "failed",
        "rhythm_density_insight_id": None,
        "finding": None,
        "reasons": ["persisted Insights could not be loaded"],
    }
    assert "private persistence detail" not in failed.text


def test_density_owner_version_must_be_in_authorized_work(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, _ = _snapshot()
    _install_snapshot(monkeypatch, snapshot)
    insight_calls = _install_insights(monkeypatch, [])
    monkeypatch.setattr(relation_api, "get_supabase", lambda: SimpleNamespace())

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/rhythm-density-context",
        json=_body(uuid4()),
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["finding"] is None
    assert "authorized Work snapshot" in response.json()["reasons"][0]
    assert insight_calls == []


def test_unknown_work_stays_404(client, monkeypatch, override_auth):
    class MissingWorkBundleRepository:
        def __init__(self, client):
            self.client = client

        def load(self, work_id, owner_id):
            return None

    monkeypatch.setattr(relation_api, "WorkBundleRepository", MissingWorkBundleRepository)
    monkeypatch.setattr(relation_api, "get_supabase", lambda: SimpleNamespace())

    response = client.post(
        f"/api/v1/works/{uuid4()}/relations/rhythm-density-context",
        json=_body(uuid4()),
        headers=AUTH_HEADER,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Work not found"

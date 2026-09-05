from types import SimpleNamespace
from uuid import uuid4

import pytest

import domain.relation_api as relation_api
from auth_utils import verify_token
from domain.models import Artifact, ArtifactKind, Version, Work
from domain.similar_moments_query import SimilarMomentsQueryResult
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


def _snapshot():
    work = Work(project_id=uuid4(), title="Similar moments API")
    artifact = Artifact(
        work_id=work.id,
        kind=ArtifactKind.audio_original,
        mime_type="audio/wav",
    )
    version = Version(
        artifact_id=artifact.id,
        storage_key="source.wav",
        storage_bucket="artifacts",
        created_by="owner-1",
        label="source.wav",
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


def _install_snapshot(monkeypatch, snapshot):
    class FakeWorkBundleRepository:
        def __init__(self, client):
            self.client = client

        def load(self, work_id, owner_id):
            assert work_id == snapshot.work.id
            assert owner_id == "owner-1"
            return snapshot

    monkeypatch.setattr(relation_api, "WorkBundleRepository", FakeWorkBundleRepository)
    monkeypatch.setattr(relation_api, "get_supabase", lambda: SimpleNamespace())


def test_route_passes_exact_selected_span_and_source_version(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, source_version = _snapshot()
    _install_snapshot(monkeypatch, snapshot)
    calls = []

    def fake_find(snapshot_arg, *, source_version, query, load_report):
        calls.append((snapshot_arg, source_version, query, load_report))
        return SimilarMomentsQueryResult(
            status="unavailable",
            reasons=["probe result"],
        )

    monkeypatch.setattr(relation_api, "find_persisted_similar_moments", fake_find)

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/similar-moments",
        json={
            "source_version_id": str(source_version.id),
            "query_start_seconds": 12.25,
            "query_end_seconds": 18.5,
            "max_matches": 3,
        },
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "unavailable",
        "evidence_report_version_id": None,
        "observation": None,
        "reasons": ["probe result"],
    }
    assert len(calls) == 1
    snapshot_arg, called_source, query, _ = calls[0]
    assert snapshot_arg is snapshot
    assert called_source.id == source_version.id
    assert query.query_start_seconds == 12.25
    assert query.query_end_seconds == 18.5
    assert query.max_matches == 3


def test_route_rejects_source_version_outside_requested_work(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, _ = _snapshot()
    _install_snapshot(monkeypatch, snapshot)

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/similar-moments",
        json={
            "source_version_id": str(uuid4()),
            "query_start_seconds": 1.0,
            "query_end_seconds": 3.0,
        },
        headers=AUTH_HEADER,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source version not found in work"


def test_route_rejects_unbounded_candidate_count_before_query(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, source_version = _snapshot()
    _install_snapshot(monkeypatch, snapshot)

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/similar-moments",
        json={
            "source_version_id": str(source_version.id),
            "query_start_seconds": 1.0,
            "query_end_seconds": 3.0,
            "max_matches": 99,
        },
        headers=AUTH_HEADER,
    )

    assert response.status_code == 422

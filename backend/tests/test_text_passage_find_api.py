from types import SimpleNamespace
from uuid import uuid4

import pytest

import domain.relation_api as relation_api
from auth_utils import verify_token
from domain.models import Artifact, ArtifactKind, Version, Work
from domain.text_passage_find import TextPassageFindResult
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
    work = Work(project_id=uuid4(), title="Text passage Find API")
    source_artifact = Artifact(
        work_id=work.id,
        kind=ArtifactKind.audio_original,
        mime_type="audio/wav",
    )
    source_version = Version(
        artifact_id=source_artifact.id,
        storage_key="source.wav",
        storage_bucket="artifacts",
        created_by="owner-1",
        label="source.wav",
    )
    performance_artifact = Artifact(
        work_id=work.id,
        kind=ArtifactKind.midi_performance,
        mime_type="audio/midi",
    )
    performance_version = Version(
        artifact_id=performance_artifact.id,
        parent_version_id=source_version.id,
        storage_key="performance.mid",
        storage_bucket="artifacts",
        created_by="owner-1",
        label="performance.mid",
    )
    return (
        WorkBundleSnapshot(
            work=work,
            artifacts=[source_artifact, performance_artifact],
            versions_by_artifact={
                source_artifact.id: [source_version],
                performance_artifact.id: [performance_version],
            },
            jobs=[],
        ),
        source_version,
        performance_version,
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


def test_route_passes_exact_source_performance_and_text_query(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, source_version, performance_version = _snapshot()
    _install_snapshot(monkeypatch, snapshot)
    calls = []

    def fake_find(
        snapshot_arg,
        *,
        source_version,
        performance_version,
        query,
        load_performance,
        retrieve,
    ):
        calls.append(
            (
                snapshot_arg,
                source_version,
                performance_version,
                query,
                load_performance,
                retrieve,
            )
        )
        return TextPassageFindResult(
            status="unavailable",
            reasons=["probe result"],
        )

    monkeypatch.setattr(relation_api, "find_text_passages", fake_find)

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/text-passages",
        json={
            "source_version_id": str(source_version.id),
            "performance_version_id": str(performance_version.id),
            "text": "sparse piano",
            "max_matches": 3,
        },
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "unavailable",
        "observation": None,
        "reasons": ["probe result"],
    }
    assert len(calls) == 1
    snapshot_arg, called_source, called_performance, query, _, retrieve = calls[0]
    assert snapshot_arg is snapshot
    assert called_source.id == source_version.id
    assert called_performance.id == performance_version.id
    assert query.text == "sparse piano"
    assert query.max_matches == 3
    assert retrieve is relation_api.retrieve_clamp3_c2


def test_route_rejects_source_or_performance_version_outside_requested_work(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, source_version, performance_version = _snapshot()
    _install_snapshot(monkeypatch, snapshot)

    missing_source = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/text-passages",
        json={
            "source_version_id": str(uuid4()),
            "performance_version_id": str(performance_version.id),
            "text": "piano",
        },
        headers=AUTH_HEADER,
    )
    assert missing_source.status_code == 404
    assert missing_source.json()["detail"] == "Source version not found in work"

    missing_performance = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/text-passages",
        json={
            "source_version_id": str(source_version.id),
            "performance_version_id": str(uuid4()),
            "text": "piano",
        },
        headers=AUTH_HEADER,
    )
    assert missing_performance.status_code == 404
    assert missing_performance.json()["detail"] == "Performance version not found in work"


def test_route_bounds_text_and_candidate_count_before_retrieval(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, source_version, performance_version = _snapshot()
    _install_snapshot(monkeypatch, snapshot)

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/text-passages",
        json={
            "source_version_id": str(source_version.id),
            "performance_version_id": str(performance_version.id),
            "text": "piano",
            "max_matches": 99,
        },
        headers=AUTH_HEADER,
    )
    assert response.status_code == 422

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/text-passages",
        json={
            "source_version_id": str(source_version.id),
            "performance_version_id": str(performance_version.id),
            "text": "x" * 501,
        },
        headers=AUTH_HEADER,
    )
    assert response.status_code == 422

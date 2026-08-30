from types import SimpleNamespace
from uuid import uuid4

import pytest

import domain.relation_api as relation_api
from auth_utils import verify_token
from domain.models import Artifact, ArtifactKind, Version, Work
from domain.relation_query import PerceptualSpanComparisonQueryResult
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
    work = Work(project_id=uuid4(), title="Relation API test")
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


def _add_worker_report(snapshot, source_version, *, storage_key=None):
    report_artifact = Artifact(
        work_id=snapshot.work.id,
        kind=ArtifactKind.analysis_report,
        mime_type="application/json",
    )
    job_id = uuid4()
    report_version = Version(
        artifact_id=report_artifact.id,
        parent_version_id=source_version.id,
        lineage=[source_version.id],
        storage_key=storage_key or f"jobs/{job_id}/attempt-0/perceptual-series.json",
        storage_bucket="artifacts",
        created_by="owner-1",
        produced_by_job_id=job_id,
        label="Perceptual series evidence",
    )
    snapshot.artifacts.append(report_artifact)
    snapshot.versions_by_artifact[report_artifact.id] = [report_version]
    snapshot.jobs.append(SimpleNamespace(id=job_id))
    return report_version, job_id


def _body(source_version_id):
    return {
        "source_version_id": str(source_version_id),
        "subject_start_seconds": 2.0,
        "subject_end_seconds": 4.0,
        "comparison_start_seconds": 8.0,
        "comparison_end_seconds": 10.0,
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


def test_missing_persisted_evidence_returns_typed_unavailable_state(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, source_version = _snapshot()
    calls = _install_snapshot(monkeypatch, snapshot)
    fake_supabase = SimpleNamespace()
    monkeypatch.setattr(relation_api, "get_supabase", lambda: fake_supabase)

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/perceptual-span-comparison",
        json=_body(source_version.id),
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "unavailable",
        "evidence_report_version_id": None,
        "finding": None,
        "reasons": ["perceptual evidence is not available for this source Version"],
    }
    assert calls == [(snapshot.work.id, "owner-1")]


def test_source_version_must_belong_to_requested_work(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, _ = _snapshot()
    _install_snapshot(monkeypatch, snapshot)
    monkeypatch.setattr(relation_api, "get_supabase", lambda: SimpleNamespace())

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/perceptual-span-comparison",
        json=_body(uuid4()),
        headers=AUTH_HEADER,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source version not found in work"


def test_route_reads_report_only_after_storage_locator_authorization(
    client,
    monkeypatch,
    override_auth,
):
    snapshot, source_version = _snapshot()
    report_version, _ = _add_worker_report(snapshot, source_version)
    _install_snapshot(monkeypatch, snapshot)
    downloads = []

    class FakeBucket:
        def __init__(self, bucket):
            self.bucket = bucket

        def download(self, key):
            downloads.append((self.bucket, key))
            return b"report-bytes"

    class FakeStorage:
        def from_(self, bucket):
            return FakeBucket(bucket)

    monkeypatch.setattr(
        relation_api,
        "get_supabase",
        lambda: SimpleNamespace(storage=FakeStorage()),
    )

    def fake_compare(snapshot_arg, *, source_version, query, load_report):
        assert snapshot_arg is snapshot
        assert source_version.id == source_version_id
        assert query.subject_start_seconds == 2.0
        assert query.comparison_start_seconds == 8.0
        assert load_report(report_version) == b"report-bytes"
        return PerceptualSpanComparisonQueryResult(
            status="failed",
            evidence_report_version_id=report_version.id,
            reasons=["probe result"],
        )

    source_version_id = source_version.id
    monkeypatch.setattr(relation_api, "compare_persisted_perceptual_spans", fake_compare)

    response = client.post(
        f"/api/v1/works/{snapshot.work.id}/relations/perceptual-span-comparison",
        json=_body(source_version.id),
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["evidence_report_version_id"] == str(report_version.id)
    assert downloads == [("artifacts", report_version.storage_key)]


def test_report_storage_locator_is_rejected_before_privileged_download():
    snapshot, source_version = _snapshot()
    other_job_id = uuid4()
    report_version, _ = _add_worker_report(
        snapshot,
        source_version,
        storage_key=f"jobs/{other_job_id}/attempt-0/perceptual-series.json",
    )
    downloads = []

    class FakeBucket:
        def download(self, key):
            downloads.append(key)
            return b"should-not-download"

    class FakeStorage:
        def from_(self, bucket):
            return FakeBucket()

    loader = relation_api._authorized_report_loader(
        snapshot,
        SimpleNamespace(storage=FakeStorage()),
        "owner-1",
    )

    with pytest.raises(PermissionError, match="storage locator is not authorized"):
        loader(report_version)

    assert downloads == []


def test_report_version_must_be_in_authorized_snapshot_before_download():
    snapshot, source_version = _snapshot()
    report_artifact = Artifact(
        work_id=snapshot.work.id,
        kind=ArtifactKind.analysis_report,
        mime_type="application/json",
    )
    report_version = Version(
        artifact_id=report_artifact.id,
        parent_version_id=source_version.id,
        lineage=[source_version.id],
        storage_key=(
            f"owner-1/{snapshot.work.project_id}/{report_artifact.id}/perceptual-series.json"
        ),
        storage_bucket="artifacts",
        created_by="owner-1",
        label="Perceptual series evidence",
    )
    downloads = []

    class FakeBucket:
        def download(self, key):
            downloads.append(key)
            return b"should-not-download"

    class FakeStorage:
        def from_(self, bucket):
            return FakeBucket()

    loader = relation_api._authorized_report_loader(
        snapshot,
        SimpleNamespace(storage=FakeStorage()),
        "owner-1",
    )

    with pytest.raises(PermissionError, match="not in the authorized Work snapshot"):
        loader(report_version)

    assert downloads == []


def test_unknown_work_returns_404(client, monkeypatch, override_auth):
    class MissingWorkBundleRepository:
        def __init__(self, client):
            self.client = client

        def load(self, work_id, owner_id):
            return None

    monkeypatch.setattr(relation_api, "WorkBundleRepository", MissingWorkBundleRepository)
    monkeypatch.setattr(relation_api, "get_supabase", lambda: SimpleNamespace())

    work_id = uuid4()
    response = client.post(
        f"/api/v1/works/{work_id}/relations/perceptual-span-comparison",
        json=_body(uuid4()),
        headers=AUTH_HEADER,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Work not found"


@pytest.mark.asyncio
async def test_repository_validation_failure_is_not_rewritten_as_client_404(monkeypatch):
    class BrokenWorkBundleRepository:
        def __init__(self, client):
            self.client = client

        def load(self, work_id, owner_id):
            raise ValueError("sensitive persistence validation detail")

    monkeypatch.setattr(relation_api, "WorkBundleRepository", BrokenWorkBundleRepository)
    monkeypatch.setattr(relation_api, "get_supabase", lambda: SimpleNamespace())

    body = relation_api.PerceptualSpanComparisonBody(
        source_version_id=uuid4(),
        subject_start_seconds=2.0,
        subject_end_seconds=4.0,
        comparison_start_seconds=8.0,
        comparison_end_seconds=10.0,
    )
    auth = SimpleNamespace(user=SimpleNamespace(id="owner-1"))

    with pytest.raises(ValueError, match="sensitive persistence validation detail"):
        await relation_api.compare_perceptual_spans(uuid4(), body, auth)

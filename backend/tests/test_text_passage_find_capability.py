"""Worker persistence coverage for experimental CLaMP3 passage Find."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from domain.models import Artifact, ArtifactKind, Capability, Job, JobLifecycle, JobStage, Version
from domain.text_passage_find import (
    TextPassageCandidate,
    TextPassageFindObservation,
    TextPassageFindResult,
)


def test_worker_persists_exact_two_version_find_report(monkeypatch):
    from domain import text_passage_find_capability as capability

    owner = "owner-find"
    work_id = uuid4()
    source_artifact = Artifact(work_id=work_id, kind=ArtifactKind.audio_original)
    performance_artifact = Artifact(work_id=work_id, kind=ArtifactKind.midi_performance)
    source_version = Version(
        artifact_id=source_artifact.id,
        storage_key="source.wav",
        storage_bucket="artifacts",
    )
    performance_version = Version(
        artifact_id=performance_artifact.id,
        parent_version_id=source_version.id,
        lineage=[source_version.id],
        storage_key="performance.mid",
        storage_bucket="artifacts",
    )
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="text_passage_find", version="1.0"),
        lifecycle=JobLifecycle(current=JobStage.running, retry_count=1),
        input_version_ids=[source_version.id, performance_version.id],
        parameters={"text": "sparse piano", "max_matches": 2},
        created_by=owner,
    )

    created_artifacts = []
    created_versions = []

    class FakeVersionRepo:
        def __init__(self, _client):
            pass

        def get(self, version_id, _owner_id):
            return {
                source_version.id: source_version,
                performance_version.id: performance_version,
            }.get(version_id)

        def create(self, version, _owner_id):
            created_versions.append(version)
            return version

    class FakeArtifactRepo:
        def __init__(self, _client):
            pass

        def get(self, artifact_id, _owner_id):
            return {
                source_artifact.id: source_artifact,
                performance_artifact.id: performance_artifact,
            }.get(artifact_id)

        def create(self, artifact, _owner_id):
            created_artifacts.append(artifact)
            return artifact

    class FakeWorkBundleRepository:
        def __init__(self, _client):
            pass

        def load(self, loaded_work_id, loaded_owner):
            assert loaded_work_id == work_id
            assert loaded_owner == owner
            return SimpleNamespace(work=SimpleNamespace(id=work_id))

    class ProgressQuery:
        def update(self, _value):
            return self

        def eq(self, _key, _value):
            return self

        def execute(self):
            return SimpleNamespace(data=[{"ok": True}])

    class StorageBucket:
        def __init__(self, storage):
            self.storage = storage

        def download(self, key):
            assert key == "performance.mid"
            return b"MThd-performance"

        def upload(self, key, payload, options):
            self.storage.uploads.append((key, payload, options))

    class Storage:
        def __init__(self):
            self.uploads = []

        def from_(self, bucket):
            assert bucket == "artifacts"
            return StorageBucket(self)

    class FakeClient:
        def __init__(self):
            self.storage = Storage()

        def table(self, name):
            assert name == "jobs"
            return ProgressQuery()

    observation = TextPassageFindObservation(
        source_version_id=source_version.id,
        performance_version_id=performance_version.id,
        query_text="sparse piano",
        embedding_dim=768,
        duration_seconds=60.0,
        runtime_seconds=2.4,
        candidates=[
            TextPassageCandidate(
                rank=1,
                start_seconds=10.0,
                end_seconds=20.0,
                similarity=0.71,
            )
        ],
        provenance={
            "model": "CLaMP3-C2",
            "upstream_revision": "9016d2b0",
            "checkpoint_sha256": "a" * 64,
        },
    )
    result = TextPassageFindResult(status="supported", observation=observation)

    monkeypatch.setattr(capability, "VersionRepo", FakeVersionRepo)
    monkeypatch.setattr(capability, "ArtifactRepo", FakeArtifactRepo)
    monkeypatch.setattr(capability, "WorkBundleRepository", FakeWorkBundleRepository)
    monkeypatch.setattr(
        capability,
        "default_clamp3_c2_retriever",
        lambda: SimpleNamespace(retrieve=lambda *_args, **_kwargs: None),
    )

    def fake_find(snapshot, **kwargs):
        assert snapshot.work.id == work_id
        assert kwargs["source_version"].id == source_version.id
        assert kwargs["performance_version"].id == performance_version.id
        assert kwargs["query"].text == "sparse piano"
        assert kwargs["load_performance"](performance_version) == b"MThd-performance"
        return result

    monkeypatch.setattr(capability, "find_text_passages", fake_find)
    client = FakeClient()

    output_ids = capability.handle_text_passage_find(job, client)

    assert len(created_artifacts) == 1
    assert created_artifacts[0].kind == ArtifactKind.analysis_report
    assert len(created_versions) == 1
    output = created_versions[0]
    assert output.parent_version_id == source_version.id
    assert output.lineage == [source_version.id, performance_version.id]
    assert output.metadata["source_version_id"] == str(source_version.id)
    assert output.metadata["performance_version_id"] == str(performance_version.id)
    assert output.metadata["method"] == "clamp3_c2_text_performance_cosine"
    assert output.metadata["factual_truth"] is False
    assert "query_text" not in output.metadata
    assert len(output.metadata["query_sha256"]) == 64
    assert output_ids == [str(output.id)]

    assert len(client.storage.uploads) == 1
    storage_key, payload, options = client.storage.uploads[0]
    assert storage_key.endswith("/attempt-1/text-passage-find.json")
    assert options == {"content-type": "application/json"}
    persisted = json.loads(payload)
    assert persisted["observation"]["query_text"] == "sparse piano"
    assert persisted["observation"]["candidates"][0]["start_seconds"] == 10.0
    assert persisted["observation"]["candidates"][0]["similarity"] == 0.71


def test_worker_rejects_non_direct_parent_before_inference(monkeypatch):
    from domain import text_passage_find_capability as capability

    owner = "owner-find"
    work_id = uuid4()
    source_artifact = Artifact(work_id=work_id, kind=ArtifactKind.audio_original)
    performance_artifact = Artifact(work_id=work_id, kind=ArtifactKind.midi_performance)
    source_version = Version(
        artifact_id=source_artifact.id,
        storage_key="source.wav",
        storage_bucket="artifacts",
    )
    performance_version = Version(
        artifact_id=performance_artifact.id,
        parent_version_id=uuid4(),
        storage_key="performance.mid",
        storage_bucket="artifacts",
    )
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="text_passage_find", version="1.0"),
        lifecycle=JobLifecycle(current=JobStage.running),
        input_version_ids=[source_version.id, performance_version.id],
        parameters={"text": "query", "max_matches": 3},
        created_by=owner,
    )

    class FakeVersionRepo:
        def __init__(self, _client):
            pass

        def get(self, version_id, _owner_id):
            return {
                source_version.id: source_version,
                performance_version.id: performance_version,
            }.get(version_id)

    class FakeArtifactRepo:
        def __init__(self, _client):
            pass

        def get(self, artifact_id, _owner_id):
            return {
                source_artifact.id: source_artifact,
                performance_artifact.id: performance_artifact,
            }.get(artifact_id)

    monkeypatch.setattr(capability, "VersionRepo", FakeVersionRepo)
    monkeypatch.setattr(capability, "ArtifactRepo", FakeArtifactRepo)

    class ProgressQuery:
        def update(self, _value):
            return self

        def eq(self, _key, _value):
            return self

        def execute(self):
            return SimpleNamespace(data=[{"ok": True}])

    client = SimpleNamespace(table=lambda _name: ProgressQuery())

    import pytest

    with pytest.raises(ValueError, match="directly parented"):
        capability.handle_text_passage_find(job, client)

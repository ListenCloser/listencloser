from types import SimpleNamespace
from uuid import uuid4

from domain.models import Artifact, ArtifactKind, Version, Work
from domain.text_passage_find import TextPassageFindQuery, find_text_passages
from domain.work_bundle_repository import WorkBundleSnapshot


def _snapshot(*, kind=ArtifactKind.audio_original):
    work = Work(project_id=uuid4(), title="Text passage find")
    artifact = Artifact(
        work_id=work.id,
        kind=kind,
        mime_type="audio/wav" if kind == ArtifactKind.audio_original else "application/json",
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


def test_find_text_passages_preserves_exact_source_and_method_provenance():
    snapshot, source_version = _snapshot()
    calls = []

    def retrieve(source_bytes, query, *, max_matches):
        calls.append((source_bytes, query, max_matches))
        return SimpleNamespace(
            candidates=(
                SimpleNamespace(start_seconds=10.0, end_seconds=20.0, similarity=0.72),
                SimpleNamespace(start_seconds=35.0, end_seconds=45.0, similarity=0.61),
            ),
            embedding_dim=768,
            duration_seconds=90.0,
            runtime_seconds=4.2,
            provenance={
                "engine": "clamp3_text_audio",
                "upstream_revision": "pinned-revision",
                "checkpoint_sha256": "a" * 64,
                "commercial_default_eligible": False,
                "exposure": "INTERNAL_ONLY",
            },
        )

    result = find_text_passages(
        snapshot,
        source_version=source_version,
        query=TextPassageFindQuery(text="  sparse piano  ", max_matches=2),
        load_source=lambda version: b"RIFF-audio" if version.id == source_version.id else b"",
        retrieve=retrieve,
    )

    assert result.status == "supported"
    assert result.reasons == []
    assert result.observation is not None
    assert result.observation.source_version_id == source_version.id
    assert result.observation.query_text == "sparse piano"
    assert result.observation.method == "clamp3_text_audio_cosine"
    assert result.observation.embedding_dim == 768
    assert [candidate.rank for candidate in result.observation.candidates] == [1, 2]
    assert result.observation.candidates[0].similarity == 0.72
    assert result.observation.provenance["commercial_default_eligible"] is False
    assert calls == [(b"RIFF-audio", "sparse piano", 2)]


def test_find_text_passages_fails_closed_for_non_audio_source():
    snapshot, source_version = _snapshot(kind=ArtifactKind.analysis_report)
    called = False

    def retrieve(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("retrieval must not run")

    result = find_text_passages(
        snapshot,
        source_version=source_version,
        query=TextPassageFindQuery(text="piano"),
        load_source=lambda version: b"report",
        retrieve=retrieve,
    )

    assert result.status == "failed"
    assert result.reasons == ["text passage Find requires an audio source Version"]
    assert called is False


def test_find_text_passages_reports_unprovisioned_runtime_without_leaking_paths():
    snapshot, source_version = _snapshot()

    def retrieve(*args, **kwargs):
        raise RuntimeError("CLaMP3 isolated runtime is not fully pinned: /secret/path")

    result = find_text_passages(
        snapshot,
        source_version=source_version,
        query=TextPassageFindQuery(text="prominent percussion"),
        load_source=lambda version: b"audio",
        retrieve=retrieve,
    )

    assert result.status == "unavailable"
    assert result.reasons == ["CLaMP3 internal runtime is not provisioned"]


def test_find_text_passages_does_not_turn_runtime_failure_into_similarity_truth():
    snapshot, source_version = _snapshot()

    def retrieve(*args, **kwargs):
        raise RuntimeError("model produced malformed output")

    result = find_text_passages(
        snapshot,
        source_version=source_version,
        query=TextPassageFindQuery(text="calmer"),
        load_source=lambda version: b"audio",
        retrieve=retrieve,
    )

    assert result.status == "failed"
    assert result.observation is None
    assert result.reasons == ["CLaMP3 passage retrieval failed"]

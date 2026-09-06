from types import SimpleNamespace
from uuid import uuid4

from domain.models import Artifact, ArtifactKind, Version, Work
from domain.text_passage_find import TextPassageFindQuery, find_text_passages
from domain.work_bundle_repository import WorkBundleSnapshot


def _snapshot(*, source_kind=ArtifactKind.audio_original, direct_parent=True):
    work = Work(project_id=uuid4(), title="Text passage find")
    source_artifact = Artifact(
        work_id=work.id,
        kind=source_kind,
        mime_type="audio/wav" if source_kind == ArtifactKind.audio_original else "application/json",
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
        parent_version_id=source_version.id if direct_parent else uuid4(),
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


def test_find_text_passages_preserves_exact_source_performance_and_method_provenance():
    snapshot, source_version, performance_version = _snapshot()
    calls = []

    def retrieve(performance_bytes, query, *, max_matches):
        calls.append((performance_bytes, query, max_matches))
        return SimpleNamespace(
            candidates=(
                SimpleNamespace(start_seconds=10.0, end_seconds=20.0, similarity=0.72),
                SimpleNamespace(start_seconds=35.0, end_seconds=45.0, similarity=0.61),
            ),
            embedding_dim=768,
            duration_seconds=90.0,
            runtime_seconds=4.2,
            provenance={
                "engine": "clamp3_text_performance",
                "model": "CLaMP3-C2",
                "upstream_revision": "pinned-revision",
                "checkpoint_sha256": "a" * 64,
                "rights_classification": "permissive",
                "canonical_default": False,
            },
        )

    result = find_text_passages(
        snapshot,
        source_version=source_version,
        performance_version=performance_version,
        query=TextPassageFindQuery(text="  sparse piano  ", max_matches=2),
        load_performance=lambda version: (
            b"MThd-performance" if version.id == performance_version.id else b""
        ),
        retrieve=retrieve,
    )

    assert result.status == "supported"
    assert result.reasons == []
    assert result.observation is not None
    assert result.observation.source_version_id == source_version.id
    assert result.observation.performance_version_id == performance_version.id
    assert result.observation.query_text == "sparse piano"
    assert result.observation.method == "clamp3_c2_text_performance_cosine"
    assert result.observation.embedding_dim == 768
    assert [candidate.rank for candidate in result.observation.candidates] == [1, 2]
    assert result.observation.candidates[0].similarity == 0.72
    assert result.observation.provenance["rights_classification"] == "permissive"
    assert calls == [(b"MThd-performance", "sparse piano", 2)]


def test_find_text_passages_fails_closed_for_non_audio_source():
    snapshot, source_version, performance_version = _snapshot(
        source_kind=ArtifactKind.analysis_report
    )
    called = False

    def retrieve(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("retrieval must not run")

    result = find_text_passages(
        snapshot,
        source_version=source_version,
        performance_version=performance_version,
        query=TextPassageFindQuery(text="piano"),
        load_performance=lambda version: b"midi",
        retrieve=retrieve,
    )

    assert result.status == "failed"
    assert result.reasons == ["text passage Find requires an audio source Version"]
    assert called is False


def test_find_text_passages_withholds_midi_not_directly_parented_to_exact_source():
    snapshot, source_version, performance_version = _snapshot(direct_parent=False)
    called = False

    def retrieve(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("retrieval must not run")

    result = find_text_passages(
        snapshot,
        source_version=source_version,
        performance_version=performance_version,
        query=TextPassageFindQuery(text="prominent percussion"),
        load_performance=lambda version: b"midi",
        retrieve=retrieve,
    )

    assert result.status == "withheld"
    assert result.reasons == [
        "performance MIDI is not directly parented to the exact source audio Version"
    ]
    assert called is False


def test_find_text_passages_reports_unprovisioned_c2_runtime_without_leaking_paths():
    snapshot, source_version, performance_version = _snapshot()

    def retrieve(*args, **kwargs):
        raise RuntimeError("CLaMP3 C2 runtime is not fully pinned: /secret/path")

    result = find_text_passages(
        snapshot,
        source_version=source_version,
        performance_version=performance_version,
        query=TextPassageFindQuery(text="prominent percussion"),
        load_performance=lambda version: b"midi",
        retrieve=retrieve,
    )

    assert result.status == "unavailable"
    assert result.reasons == ["CLaMP3 C2 runtime is not provisioned"]


def test_find_text_passages_does_not_turn_c2_runtime_failure_into_similarity_truth():
    snapshot, source_version, performance_version = _snapshot()

    def retrieve(*args, **kwargs):
        raise RuntimeError("model produced malformed output")

    result = find_text_passages(
        snapshot,
        source_version=source_version,
        performance_version=performance_version,
        query=TextPassageFindQuery(text="calmer"),
        load_performance=lambda version: b"midi",
        retrieve=retrieve,
    )

    assert result.status == "failed"
    assert result.observation is None
    assert result.reasons == ["CLaMP3 C2 passage retrieval failed"]

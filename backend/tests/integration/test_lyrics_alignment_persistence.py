from __future__ import annotations

import json
import uuid
from uuid import UUID

import pytest

import domain.lyrics_alignment_capability as capability
from domain.lyrics_alignment import ObservedWord, build_report_from_evidence
from domain.models import (
    Artifact,
    ArtifactKind,
    Capability,
    Job,
    JobLifecycle,
    JobStage,
    Project,
    Version,
    Work,
    Workflow,
    WorkflowKind,
)
from domain.repositories import ArtifactRepo, JobRepo, ProjectRepo, VersionRepo, WorkflowRepo, WorkRepo

OWNER_ID = "00000000-0000-4000-8000-000000000181"
pytestmark = pytest.mark.real_stack


def _normalize(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _score(left: str, right: str) -> float:
    return 100.0 if left == right else 75.0


def test_supplied_text_alignment_persists_exact_lineage_and_qualified_states(sb, monkeypatch):
    project = ProjectRepo(sb).create(
        Project(owner_id=OWNER_ID, name=f"it-lyrics-{uuid.uuid4().hex[:8]}")
    )
    work = WorkRepo(sb).create(Work(project_id=project.id, title="alignment smoke"), OWNER_ID)
    artifact = ArtifactRepo(sb).create(
        Artifact(
            work_id=work.id,
            kind=ArtifactKind.audio_original,
            mime_type="audio/wav",
        ),
        OWNER_ID,
    )
    storage_key = f"it/{uuid.uuid4().hex}.wav"
    sb.storage.from_("artifacts").upload(
        storage_key,
        b"RIFFfixture-audio",
        {"content-type": "audio/wav"},
    )
    source_version = VersionRepo(sb).create(
        Version(
            artifact_id=artifact.id,
            storage_key=storage_key,
            storage_bucket="artifacts",
            label="fixture.wav",
            created_by=OWNER_ID,
        ),
        OWNER_ID,
    )
    workflow = WorkflowRepo(sb).create(
        Workflow(
            project_id=project.id,
            kind=WorkflowKind.understand,
            target_version_id=source_version.id,
        ),
        OWNER_ID,
    )
    job = Job(
        workflow_id=workflow.id,
        capability=Capability(name="lyrics_alignment", version="1.0"),
        lifecycle=JobLifecycle(current=JobStage.running),
        input_version_ids=[source_version.id],
        parameters={
            "source_text": "hello wurld\nmissing",
            "text_source_kind": "user_supplied",
            "model_name": "base",
            "match_threshold": 55.0,
            "trusted_score": 100.0,
        },
        created_by=OWNER_ID,
    )
    job = JobRepo(sb).create(job, OWNER_ID)

    def _fake_alignment(**kwargs):
        assert kwargs["version_id"] == source_version.id
        assert kwargs["source_text"] == "hello wurld\nmissing"
        return build_report_from_evidence(
            source_text=kwargs["source_text"],
            source_kind=kwargs["source_kind"],
            work_id=kwargs["work_id"],
            artifact_id=kwargs["artifact_id"],
            version_id=kwargs["version_id"],
            transcript=[
                ObservedWord("hello", "hello", 1.0, 1.4),
                ObservedWord("world", "world", 1.5, 1.9),
            ],
            mapping={0: 0, 1: 1},
            score_word_pair=_score,
            normalize=_normalize,
            model_name="base",
            match_threshold=55.0,
            trusted_score=100.0,
        )

    monkeypatch.setattr(capability, "align_supplied_text", _fake_alignment)

    output_ids = capability.handle_lyrics_alignment(job, sb)
    assert len(output_ids) == 1

    output_version = VersionRepo(sb).get(UUID(output_ids[0]), OWNER_ID)
    assert output_version is not None
    assert output_version.parent_version_id == source_version.id
    assert output_version.lineage == [source_version.id]
    assert output_version.produced_by_job_id == job.id
    assert output_version.metadata["source_version_id"] == str(source_version.id)
    assert output_version.metadata["text_source_kind"] == "user_supplied"
    assert output_version.metadata["aligned_word_count"] == 1
    assert output_version.metadata["ambiguous_word_count"] == 1
    assert output_version.metadata["failed_word_count"] == 1

    payload = sb.storage.from_("artifacts").download(output_version.storage_key)
    report = json.loads(payload)
    assert report["audio_provenance"]["version_id"] == str(source_version.id)
    assert report["text_provenance"]["source_kind"] == "user_supplied"
    assert [word["status"] for word in report["words"]] == [
        "aligned",
        "ambiguous",
        "failed",
    ]
    assert report["words"][2]["start_seconds"] is None
    assert report["words"][2]["end_seconds"] is None

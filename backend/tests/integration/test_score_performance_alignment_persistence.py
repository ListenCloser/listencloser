from __future__ import annotations

import json
import uuid
from uuid import UUID

import pytest

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
from domain.repositories import (
    ArtifactRepo,
    JobRepo,
    ProjectRepo,
    VersionRepo,
    WorkflowRepo,
    WorkRepo,
)
from domain.score_performance_alignment import (
    AlignmentCoverage,
    AlignmentEventRef,
    AlignmentMethod,
    AlignmentProjectionPrecision,
    AlignmentRelationKind,
    AlignmentSufficiency,
    AlignmentSufficiencyPolicy,
    ScorePerformanceAlignment,
    ScorePerformanceEventRelation,
)
from domain.score_performance_alignment_capability import handle_score_performance_alignment
from domain.score_performance_note_identity import (
    AlignmentEventIdentity,
    PerformanceEventIdentity,
    ScoreEventIdentity,
)
from engines.alignment.parangonar import ParangonarAlignmentExecution

OWNER_ID = "00000000-0000-4000-8000-000000001083"
pytestmark = pytest.mark.real_stack


def _upload_version(sb, *, work_id, kind, mime_type, suffix, payload):
    artifact = ArtifactRepo(sb).create(
        Artifact(work_id=work_id, kind=kind, mime_type=mime_type),
        OWNER_ID,
    )
    storage_key = f"it/{uuid.uuid4().hex}.{suffix}"
    sb.storage.from_("artifacts").upload(
        storage_key,
        payload,
        {"content-type": mime_type},
    )
    version = VersionRepo(sb).create(
        Version(
            artifact_id=artifact.id,
            storage_key=storage_key,
            storage_bucket="artifacts",
            label=f"fixture.{suffix}",
            created_by=OWNER_ID,
        ),
        OWNER_ID,
    )
    return artifact, version


def test_score_performance_alignment_persists_exact_two_version_lineage(sb, monkeypatch):
    project = ProjectRepo(sb).create(
        Project(owner_id=OWNER_ID, name=f"it-alignment-{uuid.uuid4().hex[:8]}")
    )
    work = WorkRepo(sb).create(Work(project_id=project.id, title="Alignment piano smoke"), OWNER_ID)
    score_artifact, score_version = _upload_version(
        sb,
        work_id=work.id,
        kind=ArtifactKind.musicxml_score,
        mime_type="application/vnd.recordare.musicxml+xml",
        suffix="musicxml",
        payload=b"<score-partwise version='4.0'></score-partwise>",
    )
    _, performance_version = _upload_version(
        sb,
        work_id=work.id,
        kind=ArtifactKind.midi_performance,
        mime_type="audio/midi",
        suffix="mid",
        payload=b"MThd" + b"\x00" * 10,
    )
    workflow = WorkflowRepo(sb).create(
        Workflow(
            project_id=project.id,
            kind=WorkflowKind.understand,
            target_version_id=score_version.id,
        ),
        OWNER_ID,
    )
    job = JobRepo(sb).create(
        Job(
            workflow_id=workflow.id,
            capability=Capability(name="score_performance_alignment", version="1.0"),
            lifecycle=JobLifecycle(current=JobStage.running),
            input_version_ids=[score_version.id, performance_version.id],
            created_by=OWNER_ID,
        ),
        OWNER_ID,
    )

    relation = ScorePerformanceAlignment(
        score_version_id=score_version.id,
        performance_version_id=performance_version.id,
        method=AlignmentMethod(
            package="parangonar",
            package_version="3.3.3",
            matcher="DualDTWNoteMatcher",
            parameters={"process_ornaments": False, "identity_fields": "partitura_native_v1"},
        ),
        relations=(
            ScorePerformanceEventRelation(
                kind=AlignmentRelationKind.matched,
                score_events=(AlignmentEventRef(event_id="s1", onset_beat=4.0),),
                performance_events=(AlignmentEventRef(event_id="p1", onset_seconds=2.25),),
            ),
        ),
        coverage=AlignmentCoverage(
            score_events_total=1,
            performance_events_total=1,
            score_events_mapped=1,
            performance_events_mapped=1,
        ),
        sufficiency_policy=AlignmentSufficiencyPolicy(
            minimum_score_fraction=0.8,
            minimum_performance_fraction=0.8,
        ),
        sufficiency=AlignmentSufficiency.sufficient,
        projection_precision=AlignmentProjectionPrecision.adequate,
    )
    event_identity = AlignmentEventIdentity(
        score_events=(
            ScoreEventIdentity(
                event_id="s1",
                measure_index=1,
                pitch=64,
                onset_beat=4.0,
                duration_beat=1.0,
                onset_quarter=4.0,
                duration_quarter=1.0,
                onset_div=1920,
                duration_div=480,
                voice=1,
                staff=1,
                is_grace=False,
                rel_onset_div=0,
                total_measure_divs=1920,
            ),
        ),
        performance_events=(
            PerformanceEventIdentity(
                event_id="p1",
                pitch=64,
                onset_seconds=2.25,
                duration_seconds=0.45,
                velocity=91,
                track=0,
                channel=0,
            ),
        ),
    )

    def fake_align_with_identity(_self, **kwargs):
        assert kwargs["score_version_id"] == score_version.id
        assert kwargs["performance_version_id"] == performance_version.id
        assert kwargs["sufficiency_policy"].minimum_score_fraction == 0.8
        return ParangonarAlignmentExecution(relation=relation, event_identity=event_identity)

    monkeypatch.setattr(
        "domain.score_performance_alignment_capability.ParangonarAlignmentEngine.align_with_identity",
        fake_align_with_identity,
    )

    output_ids = handle_score_performance_alignment(job, sb)
    assert len(output_ids) == 1
    output_version = VersionRepo(sb).get(UUID(output_ids[0]), OWNER_ID)
    assert output_version is not None
    assert output_version.parent_version_id == score_version.id
    assert output_version.lineage == [score_version.id, performance_version.id]
    assert output_version.produced_by_job_id == job.id
    assert output_version.metadata["report_type"] == "score_performance_alignment"
    assert output_version.metadata["schema_version"] == 2
    assert output_version.metadata["identity_schema_version"] == 1
    assert output_version.metadata["score_version_id"] == str(score_version.id)
    assert output_version.metadata["performance_version_id"] == str(performance_version.id)
    assert output_version.metadata["matcher"] == "DualDTWNoteMatcher"
    assert output_version.metadata["sufficiency"] == "sufficient"
    assert output_version.metadata["projection_precision"] == "adequate"

    output_artifact = ArtifactRepo(sb).get(output_version.artifact_id, OWNER_ID)
    assert output_artifact is not None
    assert output_artifact.kind == ArtifactKind.analysis_report
    assert output_artifact.work_id == score_artifact.work_id

    payload = json.loads(sb.storage.from_("artifacts").download(output_version.storage_key))
    assert payload["score_version_id"] == str(score_version.id)
    assert payload["performance_version_id"] == str(performance_version.id)
    assert payload["relations"][0]["score_events"][0]["event_id"] == "s1"
    assert payload["relations"][0]["performance_events"][0]["event_id"] == "p1"
    assert payload["event_identity"]["schema_version"] == 1
    assert payload["event_identity"]["score_events"][0] == {
        "duration_beat": 1.0,
        "duration_div": 480,
        "duration_quarter": 1.0,
        "event_id": "s1",
        "is_grace": False,
        "measure_index": 1,
        "onset_beat": 4.0,
        "onset_div": 1920,
        "onset_quarter": 4.0,
        "pitch": 64,
        "rel_onset_div": 0,
        "staff": 1,
        "total_measure_divs": 1920,
        "voice": 1,
    }
    assert payload["event_identity"]["performance_events"][0]["event_id"] == "p1"
    assert payload["event_identity"]["performance_events"][0]["pitch"] == 64
    assert payload["event_identity"]["performance_events"][0]["onset_seconds"] == 2.25

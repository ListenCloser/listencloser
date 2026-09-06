from __future__ import annotations

import io
import uuid

import pretty_midi
import pytest

import domain.api.workflows_jobs as workflows_jobs
import domain.capabilities as capabilities
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

OWNER_ID = "00000000-0000-4000-8000-000000000101"

pytestmark = pytest.mark.real_stack


def _fixture_midi() -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    piano = pretty_midi.Instrument(program=0, name="Piano")
    piano.notes.extend(
        [
            pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.4),
            pretty_midi.Note(velocity=84, pitch=64, start=0.5, end=0.9),
        ]
    )
    midi.instruments.append(piano)
    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def _seed_correction(sb):
    project = ProjectRepo(sb).create(
        Project(owner_id=OWNER_ID, name=f"it-correction-{uuid.uuid4().hex[:8]}")
    )
    work = WorkRepo(sb).create(Work(project_id=project.id, title="correction lineage"), OWNER_ID)
    artifact = ArtifactRepo(sb).create(
        Artifact(work_id=work.id, kind=ArtifactKind.midi_performance, mime_type="audio/midi"),
        OWNER_ID,
    )
    source = VersionRepo(sb).create(
        Version(
            artifact_id=artifact.id,
            storage_key=f"it/{uuid.uuid4().hex}.mid",
            storage_bucket="artifacts",
            label="Source transcription",
        ),
        OWNER_ID,
    )
    workflow = WorkflowRepo(sb).create(
        Workflow(project_id=project.id, kind=WorkflowKind.correct, target_version_id=source.id),
        OWNER_ID,
    )
    job = Job(
        workflow_id=workflow.id,
        capability=Capability(name="correct", version="1.0"),
        lifecycle=JobLifecycle(current=JobStage.running),
        input_version_ids=[source.id],
        parameters={
            "selection_start": 0.0,
            "selection_end": 0.4,
            "corrected_notes": [
                {"pitch": 61, "start": 0.0, "end": 0.4, "velocity": 80},
            ],
        },
    )
    JobRepo(sb).create(job, OWNER_ID)
    return work, source, job


def test_correct_handler_persists_exact_parent_job_and_work_lineage(sb, monkeypatch) -> None:
    work, source, job = _seed_correction(sb)
    source_before = (
        sb.table("artifact_versions").select("*").eq("id", str(source.id)).single().execute().data
    )

    monkeypatch.setattr(capabilities, "download_version_bytes", lambda *_args: _fixture_midi())
    monkeypatch.setattr(capabilities, "_upload_bytes", lambda *_args, **_kwargs: None)

    outputs = capabilities.handle_correct(job, sb)

    assert len(outputs) == 1
    corrected_id = outputs[0]
    assert corrected_id != str(source.id)

    corrected = (
        sb.table("artifact_versions").select("*").eq("id", corrected_id).single().execute().data
    )
    corrected_artifact = (
        sb.table("artifacts")
        .select("work_id,kind")
        .eq("id", corrected["artifact_id"])
        .single()
        .execute()
        .data
    )
    source_after = (
        sb.table("artifact_versions").select("*").eq("id", str(source.id)).single().execute().data
    )

    assert corrected["parent_version_id"] == str(source.id)
    assert corrected["lineage"] == [str(source.id)]
    assert corrected["produced_by_job_id"] == str(job.id)
    assert corrected_artifact == {"work_id": str(work.id), "kind": "midi_corrected"}
    assert source_after == source_before, "correction must never mutate the source Version"


def test_correct_api_queues_the_exact_requested_source_version(monkeypatch) -> None:
    source_version_id = uuid.uuid4()
    project_id = uuid.uuid4()
    captured: dict[str, object] = {}
    fake_sb = object()

    monkeypatch.setattr(workflows_jobs, "supabase_client", lambda: fake_sb)
    monkeypatch.setattr(workflows_jobs, "owner_id", lambda _auth: OWNER_ID)

    def require_version(sb, version_id, requested_project_id, owner):
        captured["require"] = (sb, version_id, requested_project_id, owner)
        return Version(
            id=version_id,
            artifact_id=uuid.uuid4(),
            storage_key="source.mid",
            storage_bucket="artifacts",
        )

    monkeypatch.setattr(workflows_jobs, "_require_version_in_project", require_version)

    class CapturingWorkflowRepo:
        def __init__(self, sb):
            assert sb is fake_sb

        def create(self, workflow, owner):
            captured["workflow"] = workflow
            captured["workflow_owner"] = owner
            return workflow

    class CapturingJobRepo:
        def __init__(self, sb):
            assert sb is fake_sb

        def create(self, job, owner):
            captured["job"] = job
            captured["job_owner"] = owner
            return job

    monkeypatch.setattr(workflows_jobs, "WorkflowRepo", CapturingWorkflowRepo)
    monkeypatch.setattr(workflows_jobs, "JobRepo", CapturingJobRepo)

    body = workflows_jobs.CorrectWorkflowBody(
        version_id=str(source_version_id),
        project_id=str(project_id),
        selection_start=1.0,
        selection_end=1.5,
        corrected_notes=[{"pitch": 65, "start": 1.0, "end": 1.5, "velocity": 90}],
    )
    result = workflows_jobs.create_correct_workflow(body, request=object(), auth=object())

    workflow = captured["workflow"]
    job = captured["job"]
    assert isinstance(workflow, Workflow)
    assert isinstance(job, Job)
    assert result == {"workflow": workflow, "job": job}
    assert captured["require"] == (fake_sb, source_version_id, project_id, OWNER_ID)
    assert captured["workflow_owner"] == OWNER_ID
    assert workflow.project_id == project_id
    assert workflow.kind == WorkflowKind.correct
    assert workflow.target_version_id == source_version_id
    assert captured["job_owner"] == OWNER_ID
    assert job.capability.name == "correct"
    assert job.input_version_ids == [source_version_id]
    assert job.parameters == {
        "corrected_notes": [{"pitch": 65, "start": 1.0, "end": 1.5, "velocity": 90}],
        "selection_start": 1.0,
        "selection_end": 1.5,
    }

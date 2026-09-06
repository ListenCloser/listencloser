"""Explicit user-triggered alternate Harmony interpretation workflow."""

from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth_utils import limiter, verify_token
from domain.api.dependencies import owner_id, supabase_client
from domain.api_schemas import WorkflowJobResponse
from domain.models import Capability, Job, Workflow, WorkflowKind
from domain.repositories import ArtifactRepo, JobRepo, VersionRepo, WorkflowRepo, WorkRepo

router = APIRouter()


class HarmonyInterpretationBody(BaseModel):
    performance_midi_version_id: str
    source_audio_version_id: str
    harmony_engine: Literal["chordmini"] = "chordmini"


def _version_for_work(sb, version_id: UUID, work_id: UUID, owner: str):
    version = VersionRepo(sb).get(version_id, owner)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    artifact = ArtifactRepo(sb).get(version.artifact_id, owner)
    if not artifact or artifact.work_id != work_id:
        raise HTTPException(status_code=400, detail="Version does not belong to this Work")
    return version, artifact


@router.post(
    "/works/{work_id}/workflows/harmony-interpretation",
    response_model=WorkflowJobResponse,
)
@limiter.limit("5/minute")
def create_harmony_interpretation_workflow(
    work_id: UUID,
    body: HarmonyInterpretationBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Queue ChordMini over one exact audio Version and publish onto one exact MIDI Version."""
    sb = supabase_client()
    owner = owner_id(auth)

    try:
        work = WorkRepo(sb).get(work_id, owner)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

        midi_id = UUID(body.performance_midi_version_id)
        audio_id = UUID(body.source_audio_version_id)
        midi_version, midi_artifact = _version_for_work(sb, midi_id, work_id, owner)
        audio_version, audio_artifact = _version_for_work(sb, audio_id, work_id, owner)

        if str(midi_artifact.kind) not in {"ArtifactKind.midi_performance", "ArtifactKind.midi_corrected", "midi_performance", "midi_corrected"}:
            raise HTTPException(status_code=400, detail="Harmony interpretation requires a Piano Roll MIDI Version")
        if str(audio_artifact.kind) not in {"ArtifactKind.audio_original", "audio_original"}:
            raise HTTPException(status_code=400, detail="Harmony interpretation requires the original audio Version")

        engine = body.harmony_engine
        job_id = uuid5(
            NAMESPACE_URL,
            f"listencloser:harmony-interpretation:1.0:{owner}:{midi_id}:{audio_id}:{engine}",
        )
        job_repo = JobRepo(sb)
        existing = job_repo.get(job_id, owner)
        if existing:
            workflow = WorkflowRepo(sb).get(existing.workflow_id, owner)
            if not workflow:
                raise RuntimeError("idempotent Harmony job references a missing workflow")
            return {"workflow": workflow, "job": existing}

        workflow_id = uuid5(
            NAMESPACE_URL,
            f"listencloser:harmony-interpretation-workflow:1.0:{owner}:{midi_id}:{audio_id}:{engine}",
        )
        workflow_repo = WorkflowRepo(sb)
        workflow = Workflow(
            id=workflow_id,
            project_id=work.project_id,
            kind=WorkflowKind.understand,
            target_version_id=midi_id,
            parameters={
                "workflow_scope": "harmony_interpretation",
                "harmony_engine": engine,
                "source_audio_version_id": str(audio_id),
            },
        )
        try:
            workflow = workflow_repo.create(workflow, owner)
        except Exception:
            workflow = workflow_repo.get(workflow_id, owner)
            if not workflow:
                raise

        fmt = Path(audio_version.label).suffix.lstrip(".").lower() or "wav"
        job = Job(
            id=job_id,
            workflow_id=workflow.id,
            capability=Capability(name="harmony_interpretation", version="1.0"),
            input_version_ids=[midi_version.id, audio_version.id],
            parameters={"harmony_engine": engine, "fmt": fmt},
            cache_key=f"harmony-interpretation:1.0:{owner}:{midi_id}:{audio_id}:{engine}",
            created_by=owner,
        )
        try:
            job = job_repo.create(job, owner)
        except Exception:
            job = job_repo.get(job_id, owner)
            if not job:
                raise
        return {"workflow": workflow, "job": job}
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

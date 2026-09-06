"""Durable workflow entrypoint for experimental text-to-passage Find."""

from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth_utils import limiter, verify_token
from domain.api.dependencies import owner_id, supabase_client
from domain.api_schemas import WorkflowJobResponse
from domain.models import ArtifactKind, Capability, Job, Version, Workflow, WorkflowKind
from domain.repositories import ArtifactRepo, JobRepo, VersionRepo, WorkflowRepo, WorkRepo

router = APIRouter()
_ALLOWED_SOURCE_KINDS = {
    ArtifactKind.audio_original,
    ArtifactKind.audio_enhanced,
    ArtifactKind.audio_rendered,
}


class TextPassageFindWorkflowBody(BaseModel):
    """Queue one text query over one exact audio/performance Version pair."""

    source_version_id: UUID
    performance_version_id: UUID
    project_id: UUID
    text: str = Field(min_length=1, max_length=500)
    max_matches: int = Field(default=3, ge=1, le=5)


def _require_version_in_project(
    sb,
    version_id: UUID,
    project_id: UUID,
    owner: str,
) -> Version:
    version = VersionRepo(sb).get(version_id, owner)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    artifact = ArtifactRepo(sb).get(version.artifact_id, owner)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    work = WorkRepo(sb).get(artifact.work_id, owner)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    if work.project_id != project_id:
        raise HTTPException(status_code=400, detail="Version does not belong to this project")
    return version


def _validate_exact_pair(sb, source: Version, performance: Version, owner: str) -> None:
    source_artifact = ArtifactRepo(sb).get(source.artifact_id, owner)
    performance_artifact = ArtifactRepo(sb).get(performance.artifact_id, owner)
    if not source_artifact or not performance_artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if source_artifact.work_id != performance_artifact.work_id:
        raise HTTPException(status_code=400, detail="Versions do not belong to the same Work")
    if source_artifact.kind not in _ALLOWED_SOURCE_KINDS:
        raise HTTPException(status_code=400, detail="Text passage Find requires source audio")
    if performance_artifact.kind != ArtifactKind.midi_performance:
        raise HTTPException(
            status_code=400,
            detail="Text passage Find requires performance MIDI",
        )
    if performance.parent_version_id != source.id:
        raise HTTPException(
            status_code=400,
            detail="Performance MIDI is not directly parented to the exact source audio Version",
        )


@router.post("/workflows/text-passage-find", response_model=WorkflowJobResponse)
@limiter.limit("5/minute")
def create_text_passage_find_workflow(
    body: TextPassageFindWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Queue CLaMP3 C2 retrieval instead of blocking an API request on model inference."""

    sb = supabase_client()
    owner = owner_id(auth)
    normalized_text = body.text.strip()
    if not normalized_text:
        raise HTTPException(status_code=400, detail="Text query must not be empty")

    source = _require_version_in_project(
        sb,
        body.source_version_id,
        body.project_id,
        owner,
    )
    performance = _require_version_in_project(
        sb,
        body.performance_version_id,
        body.project_id,
        owner,
    )
    _validate_exact_pair(sb, source, performance, owner)

    identity = (
        f"{owner}:{source.id}:{performance.id}:{normalized_text}:{body.max_matches}"
    )
    job_id = uuid5(NAMESPACE_URL, f"listencloser:text-passage-find:1.0:{identity}")
    workflow_id = uuid5(
        NAMESPACE_URL,
        f"listencloser:text-passage-find-workflow:1.0:{identity}",
    )
    job_repo = JobRepo(sb)
    workflow_repo = WorkflowRepo(sb)

    existing_job = job_repo.get(job_id, owner)
    if existing_job:
        existing_workflow = workflow_repo.get(existing_job.workflow_id, owner)
        if not existing_workflow:
            raise RuntimeError("idempotent text passage job references a missing workflow")
        return {"workflow": existing_workflow, "job": existing_job}

    parameters = {
        "text": normalized_text,
        "max_matches": body.max_matches,
        "performance_version_id": str(performance.id),
    }
    workflow = Workflow(
        id=workflow_id,
        project_id=body.project_id,
        kind=WorkflowKind.create,
        target_version_id=source.id,
        parameters={"action": "text_passage_find", **parameters},
    )
    try:
        workflow = workflow_repo.create(workflow, owner)
    except Exception:
        workflow = workflow_repo.get(workflow_id, owner)
        if not workflow:
            raise

    job = Job(
        id=job_id,
        workflow_id=workflow.id,
        capability=Capability(name="text_passage_find", version="1.0"),
        input_version_ids=[source.id, performance.id],
        parameters=parameters,
        created_by=owner,
    )
    try:
        job = job_repo.create(job, owner)
    except Exception:
        job = job_repo.get(job_id, owner)
        if not job:
            raise

    return {"workflow": workflow, "job": job}

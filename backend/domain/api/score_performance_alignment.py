"""Exact-pair workflow dispatch for Score ↔ performance alignment."""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth_utils import limiter, verify_token
from domain.api.dependencies import owner_id, supabase_client
from domain.api_schemas import WorkflowJobResponse
from domain.models import ArtifactKind, Capability, Job, Workflow, WorkflowKind
from domain.repositories import ArtifactRepo, JobRepo, VersionRepo, WorkflowRepo, WorkRepo

router = APIRouter()


class ScorePerformanceAlignmentWorkflowBody(BaseModel):
    score_version_id: str
    performance_version_id: str
    project_id: str


def _require_exact_pair(sb, *, score_version_id: UUID, performance_version_id: UUID, project_id: UUID, owner: str):
    version_repo = VersionRepo(sb)
    artifact_repo = ArtifactRepo(sb)
    work_repo = WorkRepo(sb)

    score_version = version_repo.get(score_version_id, owner)
    performance_version = version_repo.get(performance_version_id, owner)
    if not score_version or not performance_version:
        raise HTTPException(status_code=404, detail="Score or performance Version not found")

    score_artifact = artifact_repo.get(score_version.artifact_id, owner)
    performance_artifact = artifact_repo.get(performance_version.artifact_id, owner)
    if not score_artifact or not performance_artifact:
        raise HTTPException(status_code=404, detail="Score or performance Artifact not found")
    if score_artifact.kind != ArtifactKind.musicxml_score:
        raise HTTPException(status_code=400, detail="score_version_id must be a MusicXML score")
    if performance_artifact.kind != ArtifactKind.midi_performance:
        raise HTTPException(
            status_code=400,
            detail="performance_version_id must be canonical performance MIDI",
        )
    if score_artifact.work_id != performance_artifact.work_id:
        raise HTTPException(status_code=400, detail="Score and performance must belong to one Work")

    work = work_repo.get(score_artifact.work_id, owner)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    if work.project_id != project_id:
        raise HTTPException(status_code=400, detail="Versions do not belong to this project")
    return score_version, performance_version


@router.post("/workflows/score-performance-alignment", response_model=WorkflowJobResponse)
@limiter.limit("10/minute")
def create_score_performance_alignment_workflow(
    body: ScorePerformanceAlignmentWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Queue one idempotent exact-Version Score ↔ performance relation."""

    sb = supabase_client()
    owner = owner_id(auth)
    score_version_id = UUID(body.score_version_id)
    performance_version_id = UUID(body.performance_version_id)
    project_id = UUID(body.project_id)

    score_version, _ = _require_exact_pair(
        sb,
        score_version_id=score_version_id,
        performance_version_id=performance_version_id,
        project_id=project_id,
        owner=owner,
    )

    identity = f"{owner}:{score_version_id}:{performance_version_id}"
    workflow_id = uuid5(NAMESPACE_URL, f"listencloser:score-performance-alignment-workflow:1.0:{identity}")
    job_id = uuid5(NAMESPACE_URL, f"listencloser:score-performance-alignment:1.0:{identity}")
    job_repo = JobRepo(sb)
    existing_job = job_repo.get(job_id, owner)
    if existing_job:
        workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner)
        if not workflow:
            raise RuntimeError("idempotent alignment job references a missing workflow")
        return {"workflow": workflow, "job": existing_job}

    workflow_repo = WorkflowRepo(sb)
    workflow = Workflow(
        id=workflow_id,
        project_id=project_id,
        kind=WorkflowKind.understand,
        target_version_id=score_version.id,
        parameters={
            "score_version_id": str(score_version_id),
            "performance_version_id": str(performance_version_id),
        },
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
        capability=Capability(name="score_performance_alignment", version="1.0"),
        input_version_ids=[score_version_id, performance_version_id],
        cache_key=f"score-performance-alignment:1.0:{score_version_id}:{performance_version_id}",
        created_by=owner,
    )
    try:
        job = job_repo.create(job, owner)
    except Exception:
        job = job_repo.get(job_id, owner)
        if not job:
            raise
    return {"workflow": workflow, "job": job}

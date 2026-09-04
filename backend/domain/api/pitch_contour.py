"""Opt-in API route for the experimental continuous-pitch capability."""

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


class PitchContourWorkflowBody(BaseModel):
    version_id: str


@router.post("/workflows/pitch-contour", response_model=WorkflowJobResponse)
@limiter.limit("5/minute")
def create_pitch_contour_workflow(
    body: PitchContourWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Queue pYIN for one saved audio Version without touching normal Understand."""
    sb = supabase_client()
    owner = owner_id(auth)
    version_id = UUID(body.version_id)

    try:
        version = VersionRepo(sb).get(version_id, owner)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        artifact = ArtifactRepo(sb).get(version.artifact_id, owner)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        if artifact.kind not in {ArtifactKind.audio_original, ArtifactKind.audio_enhanced}:
            raise HTTPException(
                status_code=400,
                detail="Pitch contour requires an original or enhanced audio version",
            )
        work = WorkRepo(sb).get(artifact.work_id, owner)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

        job_id = uuid5(
            NAMESPACE_URL,
            f"listencloser:pitch-contour:1.0:pyin:{owner}:{version_id}",
        )
        job_repo = JobRepo(sb)
        existing_job = job_repo.get(job_id, owner)
        if existing_job:
            existing_workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner)
            if not existing_workflow:
                raise RuntimeError("idempotent pitch-contour job references a missing workflow")
            return {"workflow": existing_workflow, "job": existing_job}

        workflow = Workflow(
            id=uuid5(
                NAMESPACE_URL,
                f"listencloser:pitch-contour-workflow:1.0:pyin:{owner}:{version_id}",
            ),
            project_id=work.project_id,
            kind=WorkflowKind.understand,
            target_version_id=version_id,
            parameters={
                "workflow_scope": "pitch_contour",
                "status": "experimental",
                "engine": "librosa",
                "method": "pyin",
            },
        )
        workflow_repo = WorkflowRepo(sb)
        try:
            workflow = workflow_repo.create(workflow, owner)
        except Exception:
            workflow = workflow_repo.get(workflow.id, owner)
            if not workflow:
                raise

        job = Job(
            id=job_id,
            workflow_id=workflow.id,
            capability=Capability(name="pitch_contour", version="1.0"),
            input_version_ids=[version_id],
            parameters={
                "engine": "librosa",
                "method": "pyin",
                "status": "experimental",
            },
            cache_key=f"pitch_contour:1.0:pyin:{owner}:{version_id}",
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

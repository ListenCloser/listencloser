"""Typed API entry point for supplied-text audio alignment."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth_utils import limiter, verify_token
from domain.api.dependencies import owner_id, supabase_client
from domain.api.workflows_jobs import _require_version_in_project
from domain.api_schemas import WorkflowJobResponse
from domain.lyrics_alignment_report import LyricsAlignmentRequest, TextSourceKind
from domain.models import Capability, Job, Workflow, WorkflowKind
from domain.repositories import JobRepo, WorkflowRepo

router = APIRouter()


class LyricsAlignmentWorkflowBody(BaseModel):
    version_id: str
    project_id: str
    text: str = Field(min_length=1, max_length=50_000)
    text_source: TextSourceKind
    text_source_reference: str | None = Field(default=None, max_length=500)
    language: str = "en"
    ambiguity_threshold: float = Field(default=0.55, ge=0.0, le=1.0)


@router.post("/workflows/lyrics-alignment", response_model=WorkflowJobResponse)
@limiter.limit("5/minute")
def create_lyrics_alignment_workflow(
    body: LyricsAlignmentWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Queue alignment of caller-supplied/licensed text to one exact audio Version."""
    sb = supabase_client()
    owner = owner_id(auth)
    try:
        version_id = UUID(body.version_id)
        project_id = UUID(body.project_id)
        _require_version_in_project(sb, version_id, project_id, owner)
        alignment_request = LyricsAlignmentRequest.model_validate(
            {
                "text": body.text,
                "text_source": body.text_source,
                "text_source_reference": body.text_source_reference,
                "language": body.language,
                "ambiguity_threshold": body.ambiguity_threshold,
            }
        )
        parameters = alignment_request.model_dump()

        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.create,
            target_version_id=version_id,
            parameters={
                "action": "lyrics_alignment",
                "text_source": alignment_request.text_source,
                "text_source_reference": alignment_request.text_source_reference,
                "language": alignment_request.language,
            },
        )
        workflow = WorkflowRepo(sb).create(workflow, owner)

        job = Job(
            workflow_id=workflow.id,
            capability=Capability(name="lyrics_alignment", version="1.0"),
            input_version_ids=[version_id],
            parameters=parameters,
            created_by=owner,
        )
        job = JobRepo(sb).create(job, owner)
        return {"workflow": workflow, "job": job}
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

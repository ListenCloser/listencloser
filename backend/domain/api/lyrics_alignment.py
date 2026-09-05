"""HTTP entrypoint for experimental user-supplied text alignment."""

from __future__ import annotations

import hashlib
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth_utils import limiter, verify_token
from domain.api.dependencies import owner_id, supabase_client
from domain.api_schemas import WorkflowJobResponse
from domain.lyrics_alignment import (
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_MODEL,
    DEFAULT_TRUSTED_SCORE,
)
from domain.models import ArtifactKind, Capability, Job, Version, Workflow, WorkflowKind
from domain.repositories import ArtifactRepo, JobRepo, VersionRepo, WorkflowRepo, WorkRepo

router = APIRouter()

TextSourceKind = Literal["user_supplied", "licensed", "public_domain", "other_permitted"]
_ALLOWED_INPUT_KINDS = {
    ArtifactKind.audio_original,
    ArtifactKind.audio_enhanced,
    ArtifactKind.audio_rendered,
}


class SuppliedTextAlignmentBody(BaseModel):
    version_id: str
    project_id: str
    text: str = Field(min_length=1, max_length=100_000)
    text_source_kind: TextSourceKind = "user_supplied"
    language: str | None = Field(default=None, max_length=16)


def _require_audio_version_in_project(
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
    if artifact.kind not in _ALLOWED_INPUT_KINDS:
        raise HTTPException(
            status_code=400,
            detail="Supplied-text alignment requires an audio Version",
        )
    return version


@router.post(
    "/workflows/supplied-text-alignments",
    response_model=WorkflowJobResponse,
)
@limiter.limit("10/minute")
def create_supplied_text_alignment(
    body: SuppliedTextAlignmentBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Queue permitted supplied text against one exact source audio Version."""
    sb = supabase_client()
    owner = owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        _require_audio_version_in_project(sb, version_id, project_id, owner)
        source_text = body.text
        if not source_text.strip():
            raise HTTPException(status_code=400, detail="Supplied text must not be blank")
        language = body.language.strip() if body.language else None
        text_sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

        job_id = uuid5(
            NAMESPACE_URL,
            (
                "listencloser:lyrics-alignment:1.0:"
                f"{owner}:{version_id}:{body.text_source_kind}:{language}:"
                f"{DEFAULT_MODEL}:{text_sha256}"
            ),
        )
        job_repo = JobRepo(sb)
        existing_job = job_repo.get(job_id, owner)
        if existing_job:
            existing_workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner)
            if not existing_workflow:
                raise RuntimeError("idempotent lyrics-alignment job references a missing workflow")
            return {"workflow": existing_workflow, "job": existing_job}

        workflow_repo = WorkflowRepo(sb)
        workflow = Workflow(
            id=uuid5(
                NAMESPACE_URL,
                (
                    "listencloser:lyrics-alignment-workflow:1.0:"
                    f"{owner}:{version_id}:{body.text_source_kind}:{language}:"
                    f"{DEFAULT_MODEL}:{text_sha256}"
                ),
            ),
            project_id=project_id,
            kind=WorkflowKind.understand,
            target_version_id=version_id,
            parameters={
                "workflow_scope": "supplied_text_alignment",
                "text_source_kind": body.text_source_kind,
                "text_sha256": text_sha256,
                "language": language,
            },
        )
        try:
            workflow = workflow_repo.create(workflow, owner)
        except Exception:
            concurrent_job = job_repo.get(job_id, owner)
            if concurrent_job:
                concurrent_workflow = workflow_repo.get(concurrent_job.workflow_id, owner)
                if concurrent_workflow:
                    return {"workflow": concurrent_workflow, "job": concurrent_job}
            workflow = workflow_repo.get(workflow.id, owner)
            if not workflow:
                raise

        job = Job(
            id=job_id,
            workflow_id=workflow.id,
            capability=Capability(name="lyrics_alignment", version="1.0"),
            input_version_ids=[version_id],
            parameters={
                "source_text": source_text,
                "text_source_kind": body.text_source_kind,
                "language": language,
                "model_name": DEFAULT_MODEL,
                "match_threshold": DEFAULT_MATCH_THRESHOLD,
                "trusted_score": DEFAULT_TRUSTED_SCORE,
            },
            cache_key=(
                "lyrics_alignment:1.0:"
                f"{owner}:{version_id}:{body.text_source_kind}:{language}:"
                f"{DEFAULT_MODEL}:{text_sha256}"
            ),
            provenance={
                "text_sha256": text_sha256,
                "text_source_kind": body.text_source_kind,
                "source_version_id": str(version_id),
                "engine": "syncalong",
                "engine_version": "2.0.1",
                "engine_release": "v2.0.1",
                "transcription_engine": "openai-whisper",
                "transcription_engine_version": "20250625",
                "model_name": DEFAULT_MODEL,
            },
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

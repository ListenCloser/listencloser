"""
FastAPI router — domain model API endpoints for the understand workflow slice.
"""

import logging
import mimetypes
import os
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from auth_utils import limiter, verify_token
from domain.models import (
    Artifact,
    ArtifactKind,
    Capability,
    Job,
    Project,
    Version,
    Work,
    Workflow,
    WorkflowKind,
)
from domain.repositories import (
    ArtifactRepo,
    EntityRepo,
    InsightRepo,
    JobRepo,
    ProjectRepo,
    VersionRepo,
    WorkflowRepo,
    WorkRepo,
    get_supabase,
)

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger("domain.api")

_ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "m4a", "flac", "ogg", "aac"}

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateProjectBody(BaseModel):
    name: str
    description: str = ""


class CreateWorkBody(BaseModel):
    title: str
    composer: str | None = None


class UnderstandWorkflowBody(BaseModel):
    version_id: str
    project_id: str


class AnalyzeWorkflowBody(BaseModel):
    version_id: str
    project_id: str


class CorrectWorkflowBody(BaseModel):
    version_id: str
    project_id: str
    corrected_notes: list[dict]
    selection_start: float | None = None
    selection_end: float | None = None


class CompareWorkflowBody(BaseModel):
    version_id_a: str
    version_id_b: str
    project_id: str


class CreateWorkflowBody(BaseModel):
    version_id: str
    project_id: str
    action: str = "transform"
    parameters: dict = Field(default_factory=dict)


class VariationWorkflowBody(BaseModel):
    version_id: str
    project_id: str
    transpose_semitones: int = Field(ge=-12, le=12)


class JobStateResponse(BaseModel):
    id: str
    workflow_id: str
    capability: str
    stage: str
    progress: float
    message: str
    error: str | None = None
    input_version_ids: list[str]
    output_version_ids: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _owner_id(auth) -> str:
    return auth.user.id


def _sb():
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return sb


def _signed_url(storage_response) -> str:
    """Normalize the response shape across supabase-py releases."""
    data = getattr(storage_response, "data", storage_response) or {}
    if isinstance(data, dict):
        value = data.get("signedURL") or data.get("signedUrl") or data.get("signed_url")
        if value:
            return str(value)
    raise ValueError("Storage provider did not return a signed URL")


def _require_version_in_project(
    sb,
    version_id: UUID,
    project_id: UUID,
    owner_id: str,
) -> Version:
    """Verify both ownership and project membership before queuing work."""
    version = VersionRepo(sb).get(version_id, owner_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    artifact = ArtifactRepo(sb).get(version.artifact_id, owner_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    work = WorkRepo(sb).get(artifact.work_id, owner_id)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    if work.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="Version does not belong to this project",
        )
    return version


def _job_state(job: Job) -> JobStateResponse:
    return JobStateResponse(
        id=str(job.id),
        workflow_id=str(job.workflow_id),
        capability=job.capability.name,
        stage=job.lifecycle.current.value,
        progress=job.lifecycle.progress,
        message=job.lifecycle.message,
        error=job.error,
        input_version_ids=[str(version_id) for version_id in job.input_version_ids],
        output_version_ids=[str(version_id) for version_id in job.output_version_ids],
    )


# ---------------------------------------------------------------------------
# POST /projects
# ---------------------------------------------------------------------------


@router.post("/projects")
@limiter.limit("10/minute")
async def create_project(
    body: CreateProjectBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    repo = ProjectRepo(sb)
    project = Project(owner_id=owner_id, name=body.name, description=body.description)
    try:
        return repo.create(project)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# GET /projects
# ---------------------------------------------------------------------------


@router.get("/projects")
async def list_projects(
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    repo = ProjectRepo(sb)
    return repo.list_by_owner(owner_id)


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/works
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/works")
@limiter.limit("10/minute")
async def create_work(
    project_id: UUID,
    body: CreateWorkBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    repo = WorkRepo(sb)
    work = Work(project_id=project_id, title=body.title, composer=body.composer)
    try:
        return repo.create(work, owner_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/projects/{project_id}/works")
async def list_works(
    project_id: UUID,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    try:
        return WorkRepo(sb).list_by_project(project_id, owner_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/works/{work_id}")
async def get_work_bundle(
    work_id: UUID,
    auth=Depends(verify_token),
):
    """Return a work and its complete immutable artifact/version graph."""
    sb = _sb()
    owner_id = _owner_id(auth)
    try:
        work = WorkRepo(sb).get(work_id, owner_id)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

        artifacts = ArtifactRepo(sb).list_by_work(work_id, owner_id)
        items = []
        version_repo = VersionRepo(sb)
        for artifact in artifacts:
            versions = version_repo.list_by_artifact(artifact.id, owner_id)
            latest = versions[0] if versions else None
            signed_url = None
            if latest:
                try:
                    response = sb.storage.from_(latest.storage_bucket).create_signed_url(
                        latest.storage_key, 3600
                    )
                    signed_url = _signed_url(response)
                except Exception:
                    logger.warning(
                        "artifact_signed_url_failed",
                        extra={"artifact_id": str(artifact.id), "version_id": str(latest.id)},
                    )
            items.append(
                {
                    "artifact": artifact,
                    "versions": versions,
                    "latest_version": latest,
                    "signed_url": signed_url,
                }
            )
        version_ids = {version.id for item in items for version in item["versions"]}
        workflows = [
            workflow
            for workflow in WorkflowRepo(sb).list_by_project(work.project_id, owner_id)
            if workflow.target_version_id in version_ids
        ]
        jobs = [
            job
            for workflow in workflows
            for job in JobRepo(sb).list_by_workflow(workflow.id, owner_id)
        ]
        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return {"work": work, "artifacts": items, "jobs": jobs}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/works/{work_id}")
@limiter.limit("10/minute")
async def delete_work(
    work_id: UUID,
    request: Request,
    auth=Depends(verify_token),
):
    """Delete a work and its artifacts, versions, and storage objects."""
    sb = _sb()
    owner_id = _owner_id(auth)
    try:
        work_repo = WorkRepo(sb)
        work = work_repo.get(work_id, owner_id)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

        art_repo = ArtifactRepo(sb)
        ver_repo = VersionRepo(sb)
        artifacts = art_repo.list_by_work(work_id, owner_id)
        for artifact in artifacts:
            versions = ver_repo.list_by_artifact(artifact.id, owner_id)
            for version in versions:
                try:
                    sb.storage.from_(version.storage_bucket).remove([version.storage_key])
                except Exception:
                    logger.warning("storage_cleanup_skipped",
                                   extra={"version_id": str(version.id)})
            try:
                art_repo.delete(artifact.id, owner_id)
            except Exception:
                logger.exception("artifact_delete_failed")

        work_repo.delete(work_id, owner_id)
        return {"deleted": str(work_id)}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/artifacts/upload
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/artifacts/upload")
@limiter.limit("10/minute")
async def upload_artifact(
    project_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    work_id: str | None = Form(None),
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)

    try:
        proj_repo = ProjectRepo(sb)
        proj = proj_repo.get(project_id, owner_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

        filename = file.filename or "untitled"
        ext = Path(filename).suffix.lstrip(".").lower()
        if ext not in _ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail="Unsupported audio format",
            )

        max_upload_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", str(4 * 1024 * 1024)))
        raw = await file.read(max_upload_bytes + 1)
        if len(raw) > max_upload_bytes:
            raise HTTPException(status_code=413, detail="File exceeds upload size limit")
        if not raw:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        work_repo = WorkRepo(sb)
        created_work = False
        if work_id:
            w_id = UUID(work_id)
            work = work_repo.get(w_id, owner_id)
            if not work:
                raise HTTPException(status_code=404, detail="Work not found")
            if work.project_id != project_id:
                raise HTTPException(
                    status_code=400,
                    detail="Work does not belong to this project",
                )
        else:
            title = Path(filename).stem
            work = Work(project_id=project_id, title=title)
            work = work_repo.create(work, owner_id)
            created_work = True

        artifact_draft = Artifact(
            work_id=work.id,
            kind=ArtifactKind.audio_original,
            mime_type=mime_type,
        )
        art_repo = ArtifactRepo(sb)
        artifact = None
        storage_key = None
        bucket = "artifacts"
        try:
            artifact = art_repo.create(artifact_draft, owner_id)
            storage_key = f"{owner_id}/{project_id}/{artifact.id}/{uuid4().hex}.{ext}"
            sb.storage.from_(bucket).upload(storage_key, raw, {"content-type": mime_type})

            version = Version(
                artifact_id=artifact.id,
                storage_key=storage_key,
                storage_bucket=bucket,
                byte_size=len(raw),
                created_by=owner_id,
                label=filename,
            )
            version = VersionRepo(sb).create(version, owner_id)
        except Exception:
            logger.exception("upload_finalize_failed", extra={"project_id": str(project_id)})
            if storage_key:
                try:
                    sb.storage.from_(bucket).remove([storage_key])
                except Exception:
                    logger.exception("upload_storage_cleanup_failed")
            if artifact:
                try:
                    art_repo.delete(artifact.id, owner_id)
                except Exception:
                    logger.exception("upload_artifact_cleanup_failed")
            if created_work:
                try:
                    work_repo.delete(work.id, owner_id)
                except Exception:
                    logger.exception("upload_work_cleanup_failed")
            raise

        return {"artifact": artifact, "version": version}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# POST /workflows/understand
# ---------------------------------------------------------------------------


@router.post("/workflows/understand")
@limiter.limit("10/minute")
async def create_understand_workflow(
    body: UnderstandWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        version = _require_version_in_project(sb, version_id, project_id, owner_id)

        job_id = uuid5(
            NAMESPACE_URL,
            f"hello-ai:understand:1.0:{owner_id}:{version_id}",
        )
        job_repo = JobRepo(sb)
        existing_job = job_repo.get(job_id, owner_id)
        if existing_job:
            existing_workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner_id)
            if not existing_workflow:
                raise RuntimeError("idempotent job references a missing workflow")
            return {"workflow": existing_workflow, "job": existing_job}

        wf_repo = WorkflowRepo(sb)
        workflow = Workflow(
            id=uuid5(NAMESPACE_URL, f"hello-ai:understand-workflow:1.0:{owner_id}:{version_id}"),
            project_id=project_id,
            kind=WorkflowKind.understand,
            target_version_id=version_id,
        )
        try:
            workflow = wf_repo.create(workflow, owner_id)
        except Exception:
            concurrent_job = job_repo.get(job_id, owner_id)
            if concurrent_job:
                concurrent_workflow = wf_repo.get(concurrent_job.workflow_id, owner_id)
                if concurrent_workflow:
                    return {"workflow": concurrent_workflow, "job": concurrent_job}
            workflow = wf_repo.get(workflow.id, owner_id)
            if not workflow:
                raise

        job = Job(
            id=job_id,
            workflow_id=workflow.id,
            capability=Capability(name="understand", version="1.0"),
            input_version_ids=[version_id],
            parameters={"fmt": Path(version.label).suffix.lstrip(".").lower() or "wav"},
            cache_key=f"understand:1.0:{owner_id}:{version_id}",
            created_by=owner_id,
        )
        try:
            job = job_repo.create(job, owner_id)
        except Exception:
            job = job_repo.get(job_id, owner_id)
            if not job:
                raise

        return {"workflow": workflow, "job": job}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: UUID,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)

    try:
        repo = JobRepo(sb)
        job = repo.get(job_id, owner_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return _job_state(job)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/cancel")
@limiter.limit("20/minute")
async def cancel_job(
    job_id: UUID,
    request: Request,
    auth=Depends(verify_token),
):
    try:
        return _job_state(JobRepo(_sb()).cancel(job_id, _owner_id(auth)))
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/jobs/{job_id}/retry")
@limiter.limit("10/minute")
async def retry_job(
    job_id: UUID,
    request: Request,
    auth=Depends(verify_token),
):
    try:
        return _job_state(JobRepo(_sb()).retry(job_id, _owner_id(auth)))
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


# ---------------------------------------------------------------------------
# POST /workflows/analyze
# ---------------------------------------------------------------------------


@router.post("/workflows/analyze")
@limiter.limit("10/minute")
async def create_analyze_workflow(
    body: AnalyzeWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        _require_version_in_project(sb, version_id, project_id, owner_id)

        wf_repo = WorkflowRepo(sb)
        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.understand,
            target_version_id=version_id,
        )
        workflow = wf_repo.create(workflow, owner_id)

        job = Job(
            workflow_id=workflow.id,
            capability=Capability(name="analyze", version="1.0"),
            input_version_ids=[version_id],
            created_by=owner_id,
        )
        job_repo = JobRepo(sb)
        job = job_repo.create(job, owner_id)

        return {"workflow": workflow, "job": job}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# GET /versions/{version_id}
# ---------------------------------------------------------------------------


@router.get("/versions/{version_id}")
async def get_version_resource(
    version_id: UUID,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)

    try:
        version = VersionRepo(sb).get(version_id, owner_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        artifact = ArtifactRepo(sb).get(version.artifact_id, owner_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        response = sb.storage.from_(version.storage_bucket).create_signed_url(
            version.storage_key, 3600
        )
        return {
            "version": version,
            "artifact": artifact,
            "signed_url": _signed_url(response),
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# GET /versions/{version_id}/entities
# ---------------------------------------------------------------------------


@router.get("/versions/{version_id}/entities")
async def list_entities(
    version_id: UUID,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)

    try:
        repo = EntityRepo(sb)
        return repo.list_by_version(version_id, owner_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# GET /versions/{version_id}/insights
# ---------------------------------------------------------------------------


@router.get("/versions/{version_id}/insights")
async def list_insights(
    version_id: UUID,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)

    try:
        repo = InsightRepo(sb)
        return repo.list_by_version(version_id, owner_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# POST /workflows/correct
# ---------------------------------------------------------------------------


@router.post("/workflows/correct")
@limiter.limit("10/minute")
async def create_correct_workflow(
    body: CorrectWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        _require_version_in_project(sb, version_id, project_id, owner_id)

        wf_repo = WorkflowRepo(sb)
        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.correct,
            target_version_id=version_id,
        )
        workflow = wf_repo.create(workflow, owner_id)

        cache_key = f"correct:{version_id}:{body.selection_start}:{body.selection_end}"
        job = Job(
            workflow_id=workflow.id,
            capability=Capability(name="correct", version="1.0"),
            input_version_ids=[version_id],
            parameters={
                "corrected_notes": body.corrected_notes,
                "selection_start": body.selection_start,
                "selection_end": body.selection_end,
            },
            cache_key=cache_key,
            created_by=owner_id,
        )
        job_repo = JobRepo(sb)
        job = job_repo.create(job, owner_id)

        return {"workflow": workflow, "job": job}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# POST /workflows/compare
# ---------------------------------------------------------------------------


@router.post("/workflows/compare")
@limiter.limit("10/minute")
async def create_compare_workflow(
    body: CompareWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    version_id_a = UUID(body.version_id_a)
    version_id_b = UUID(body.version_id_b)
    project_id = UUID(body.project_id)

    try:
        _require_version_in_project(sb, version_id_a, project_id, owner_id)
        _require_version_in_project(sb, version_id_b, project_id, owner_id)

        wf_repo = WorkflowRepo(sb)
        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.compare,
            target_version_id=version_id_a,
            parameters={"version_id_b": body.version_id_b},
        )
        workflow = wf_repo.create(workflow, owner_id)

        job = Job(
            workflow_id=workflow.id,
            capability=Capability(name="compare", version="1.0"),
            input_version_ids=[version_id_a, version_id_b],
            created_by=owner_id,
        )
        job_repo = JobRepo(sb)
        job = job_repo.create(job, owner_id)

        return {"workflow": workflow, "job": job}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# POST /workflows/variation
# ---------------------------------------------------------------------------


@router.post("/workflows/variation")
@limiter.limit("5/minute")
async def create_variation_workflow(
    body: VariationWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Queue an idempotent, complete transposed take from a MIDI version."""
    sb = _sb()
    owner_id = _owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        _require_version_in_project(sb, version_id, project_id, owner_id)
        job_id = uuid5(
            NAMESPACE_URL,
            f"hello-ai:variation:1.0:{owner_id}:{version_id}:{body.transpose_semitones}",
        )
        job_repo = JobRepo(sb)
        existing_job = job_repo.get(job_id, owner_id)
        if existing_job:
            workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner_id)
            if not workflow:
                raise RuntimeError("idempotent job references a missing workflow")
            return {"workflow": workflow, "job": existing_job}

        workflow = Workflow(
            id=uuid5(
                NAMESPACE_URL,
                (
                    "hello-ai:variation-workflow:1.0:"
                    f"{owner_id}:{version_id}:{body.transpose_semitones}"
                ),
            ),
            project_id=project_id,
            kind=WorkflowKind.create,
            target_version_id=version_id,
            parameters={"operation": "transpose", "semitones": body.transpose_semitones},
        )
        wf_repo = WorkflowRepo(sb)
        try:
            workflow = wf_repo.create(workflow, owner_id)
        except Exception:
            workflow = wf_repo.get(workflow.id, owner_id)
            if not workflow:
                raise

        job = Job(
            id=job_id,
            workflow_id=workflow.id,
            capability=Capability(name="variation", version="1.0"),
            input_version_ids=[version_id],
            parameters={"transpose_semitones": body.transpose_semitones},
            cache_key=f"variation:1.0:{owner_id}:{version_id}:{body.transpose_semitones}",
            created_by=owner_id,
        )
        try:
            job = job_repo.create(job, owner_id)
        except Exception:
            job = job_repo.get(job_id, owner_id)
            if not job:
                raise
        return {"workflow": workflow, "job": job}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# POST /workflows/create
# ---------------------------------------------------------------------------


@router.post("/workflows/create")
@limiter.limit("5/minute")
async def create_create_workflow(
    body: CreateWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        _require_version_in_project(sb, version_id, project_id, owner_id)

        wf_repo = WorkflowRepo(sb)
        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.create,
            target_version_id=version_id,
            parameters={"action": body.action, **body.parameters},
        )
        workflow = wf_repo.create(workflow, owner_id)

        capability_name = body.action
        job = Job(
            workflow_id=workflow.id,
            capability=Capability(name=capability_name, version="1.0"),
            input_version_ids=[version_id],
            parameters=body.parameters,
            created_by=owner_id,
        )
        job_repo = JobRepo(sb)
        job = job_repo.create(job, owner_id)

        return {"workflow": workflow, "job": job}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

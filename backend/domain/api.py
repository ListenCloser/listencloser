"""
FastAPI router — domain model API endpoints for the understand workflow slice.
"""

import logging
import mimetypes
import os
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from auth_utils import limiter, verify_token
from domain.api_schemas import (
    DeletedWorkResponse,
    UploadArtifactResponse,
    VersionResourceResponse,
    WorkBundleResponse,
    WorkflowJobResponse,
)
from domain.capability_policy import is_exposed
from domain.models import (
    Artifact,
    ArtifactKind,
    Capability,
    Entity,
    Insight,
    Job,
    JobStage,
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
from domain.storage_locator_policy import classify_version_storage_locator

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
    transcription_profile: Literal["auto", "solo_piano"] | None = None


def _canonical_transcription_profile(profile: str | None) -> str:
    """Normalize the transcription profile for workflow identity.

    ``None`` (omitted) and ``"auto"`` are the same request semantically (the
    default general engine). Normalizing avoids duplicate cache entries while
    still distinguishing ``auto`` from ``solo_piano`` so re-requesting the same
    version with a different profile creates a distinct job rather than
    returning a stale cached one.
    """
    return profile or "auto"


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
    stage: JobStage
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
        stage=job.lifecycle.current,
        progress=job.lifecycle.progress,
        message=job.lifecycle.message,
        error=job.error,
        input_version_ids=[str(version_id) for version_id in job.input_version_ids],
        output_version_ids=[str(version_id) for version_id in job.output_version_ids],
    )


def _inspector_exposed(insight) -> bool:
    """Return whether a persisted Insight is safe to expose in the Inspector.

    Repositories return Pydantic ``Insight`` models, not dictionaries. Older
    endpoint code treated them as mappings and crashed with ``.get`` whenever
    a version actually had saved analysis. Unknown/stale capability kinds are
    hidden rather than turning the whole analysis request into a 500.
    """
    kind = getattr(insight, "kind", None)
    if not isinstance(kind, str) or not kind:
        return False
    try:
        return is_exposed(kind, "inspector")
    except KeyError:
        logger.warning("unregistered_insight_hidden", extra={"kind": kind})
        return False


# ---------------------------------------------------------------------------
# POST /projects
# ---------------------------------------------------------------------------


@router.post("/projects", response_model=Project)
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


@router.get("/projects", response_model=list[Project])
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


@router.post("/projects/{project_id}/works", response_model=Work)
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


@router.get("/projects/{project_id}/works", response_model=list[Work])
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


@router.get("/works/{work_id}", response_model=WorkBundleResponse)
async def get_work_bundle(
    work_id: UUID,
    auth=Depends(verify_token),
):
    """Return a work and its complete immutable artifact/version graph."""
    from domain.work_bundle_repository import WorkBundleRepository

    sb = _sb()
    owner_id = _owner_id(auth)
    try:
        snapshot = WorkBundleRepository(sb).load(work_id, owner_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Work not found")
        allowed_job_ids = {job.id for job in snapshot.jobs}

        items = []
        for artifact in snapshot.artifacts:
            versions = snapshot.versions_by_artifact.get(artifact.id, [])
            latest = versions[0] if versions else None
            signed_url = None
            if latest:
                decision = classify_version_storage_locator(
                    latest,
                    owner_id=owner_id,
                    project_id=snapshot.work.project_id,
                    artifact_id=artifact.id,
                    allowed_job_ids=allowed_job_ids,
                )
                if decision.trusted:
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
                else:
                    logger.warning(
                        "artifact_storage_locator_rejected",
                        extra={
                            "artifact_id": str(artifact.id),
                            "version_id": str(latest.id),
                            "operation": "sign",
                            "reason": decision.reason,
                        },
                    )
            items.append(
                {
                    "artifact": artifact,
                    "versions": versions,
                    "latest_version": latest,
                    "signed_url": signed_url,
                }
            )
        return {"work": snapshot.work, "artifacts": items, "jobs": snapshot.jobs}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/works/{work_id}", response_model=DeletedWorkResponse)
@limiter.limit("10/minute")
async def delete_work(
    work_id: UUID,
    request: Request,
    auth=Depends(verify_token),
):
    """Delete a work and its artifacts, versions, and storage objects."""
    from domain.work_bundle_repository import WorkBundleRepository

    sb = _sb()
    owner_id = _owner_id(auth)
    try:
        work_repo = WorkRepo(sb)
        work = work_repo.get(work_id, owner_id)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")
        snapshot = WorkBundleRepository(sb).load(work_id, owner_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Work not found")
        allowed_job_ids = {job.id for job in snapshot.jobs}

        art_repo = ArtifactRepo(sb)
        ver_repo = VersionRepo(sb)
        artifacts = art_repo.list_by_work(work_id, owner_id)
        for artifact in artifacts:
            versions = ver_repo.list_by_artifact(artifact.id, owner_id)
            for version in versions:
                decision = classify_version_storage_locator(
                    version,
                    owner_id=owner_id,
                    project_id=work.project_id,
                    artifact_id=artifact.id,
                    allowed_job_ids=allowed_job_ids,
                )
                if not decision.trusted:
                    logger.warning(
                        "artifact_storage_locator_rejected",
                        extra={
                            "artifact_id": str(artifact.id),
                            "version_id": str(version.id),
                            "operation": "delete",
                            "reason": decision.reason,
                        },
                    )
                    continue
                try:
                    sb.storage.from_(version.storage_bucket).remove([version.storage_key])
                except Exception:
                    logger.warning("storage_cleanup_skipped", extra={"version_id": str(version.id)})
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


@router.post("/projects/{project_id}/artifacts/upload", response_model=UploadArtifactResponse)
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


@router.post("/workflows/understand", response_model=WorkflowJobResponse)
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
        profile = _canonical_transcription_profile(body.transcription_profile)

        job_id = uuid5(
            NAMESPACE_URL,
            f"hello-ai:understand:1.0:{owner_id}:{version_id}:{profile}",
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
            id=uuid5(
                NAMESPACE_URL,
                f"hello-ai:understand-workflow:1.0:{owner_id}:{version_id}:{profile}",
            ),
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
            parameters={
                "fmt": Path(version.label).suffix.lstrip(".").lower() or "wav",
                "transcription_profile": profile,
            },
            cache_key=f"understand:1.0:{owner_id}:{version_id}:{profile}",
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


@router.get("/jobs/{job_id}", response_model=JobStateResponse)
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


@router.post("/jobs/{job_id}/cancel", response_model=JobStateResponse)
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


@router.post("/jobs/{job_id}/retry", response_model=JobStateResponse)
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


@router.post("/workflows/analyze", response_model=WorkflowJobResponse)
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


@router.get("/versions/{version_id}", response_model=VersionResourceResponse)
async def get_version_resource(
    version_id: UUID,
    auth=Depends(verify_token),
):
    from domain.work_bundle_repository import WorkBundleRepository

    sb = _sb()
    owner_id = _owner_id(auth)

    try:
        version = VersionRepo(sb).get(version_id, owner_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        artifact = ArtifactRepo(sb).get(version.artifact_id, owner_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        snapshot = WorkBundleRepository(sb).load(artifact.work_id, owner_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Work not found")
        decision = classify_version_storage_locator(
            version,
            owner_id=owner_id,
            project_id=snapshot.work.project_id,
            artifact_id=artifact.id,
            allowed_job_ids={job.id for job in snapshot.jobs},
        )
        if not decision.trusted:
            logger.warning(
                "artifact_storage_locator_rejected",
                extra={
                    "artifact_id": str(artifact.id),
                    "version_id": str(version.id),
                    "operation": "sign",
                    "reason": decision.reason,
                },
            )
            raise HTTPException(status_code=409, detail="Version storage resource is unavailable")
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


@router.get("/versions/{version_id}/entities", response_model=list[Entity])
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


@router.get("/versions/{version_id}/insights", response_model=list[Insight])
async def list_insights(
    version_id: UUID,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)

    try:
        repo = InsightRepo(sb)
        all_insights = repo.list_by_version(version_id, owner_id)
        # Defense-in-depth: filter by capability exposure policy even if
        # a withheld or stale insight was accidentally persisted.
        return [item for item in all_insights if _inspector_exposed(item)]
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# POST /workflows/correct
# ---------------------------------------------------------------------------


@router.post("/workflows/correct", response_model=WorkflowJobResponse)
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


@router.post("/workflows/compare", response_model=WorkflowJobResponse)
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


@router.post("/workflows/variation", response_model=WorkflowJobResponse)
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


@router.post("/workflows/create", response_model=WorkflowJobResponse)
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

"""
FastAPI router — domain model API endpoints for the understand workflow slice.
"""
import mimetypes
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from auth_utils import limiter, verify_token

from domain.models import (
    Artifact,
    ArtifactKind,
    Capability,
    Entity,
    Insight,
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
    WorkRepo,
    WorkflowRepo,
    get_supabase,
)

router = APIRouter(prefix="/api/v1")

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
    parameters: dict = {}


class JobStateResponse(BaseModel):
    stage: str
    progress: float
    error: str | None = None
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
    project = Project(
        owner_id=owner_id, name=body.name, description=body.description
    )
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

        work_repo = WorkRepo(sb)

        if work_id:
            w_id = UUID(work_id)
            work = work_repo.get(w_id, owner_id)
            if not work:
                raise HTTPException(status_code=404, detail="Work not found")
        else:
            title = Path(file.filename or "untitled").stem
            work = Work(project_id=project_id, title=title)
            work = work_repo.create(work, owner_id)

        raw = await file.read()
        filename = file.filename or "untitled"
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        artifact = Artifact(
            work_id=work.id,
            kind=ArtifactKind.audio_original,
            mime_type=mime_type,
        )
        art_repo = ArtifactRepo(sb)
        artifact = art_repo.create(artifact, owner_id)

        ext = Path(filename).suffix.lstrip(".") or "bin"
        storage_key = f"{project_id}/{artifact.id}/{uuid4().hex}.{ext}"
        bucket = "artifacts"

        sb.storage.from_(bucket).upload(
            storage_key, raw, {"content-type": mime_type}
        )

        version = Version(
            artifact_id=artifact.id,
            storage_key=storage_key,
            storage_bucket=bucket,
            byte_size=len(raw),
            created_by=owner_id,
            label=filename,
        )
        ver_repo = VersionRepo(sb)
        version = ver_repo.create(version, owner_id)

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
        ver_repo = VersionRepo(sb)
        version = ver_repo.get(version_id, owner_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

        wf_repo = WorkflowRepo(sb)
        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.understand,
            target_version_id=version_id,
        )
        workflow = wf_repo.create(workflow, owner_id)

        job = Job(
            workflow_id=workflow.id,
            capability=Capability(name="transcribe", version="1.0"),
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
        return JobStateResponse(
            stage=job.lifecycle.current.value,
            progress=job.lifecycle.progress,
            error=job.error,
            output_version_ids=[str(v) for v in job.output_version_ids],
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
        ver_repo = VersionRepo(sb)
        version = ver_repo.get(version_id, owner_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

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
        ver_repo = VersionRepo(sb)
        version = ver_repo.get(version_id, owner_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

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
        ver_repo = VersionRepo(sb)
        version_a = ver_repo.get(version_id_a, owner_id)
        if not version_a:
            raise HTTPException(status_code=404, detail="Version A not found")
        version_b = ver_repo.get(version_id_b, owner_id)
        if not version_b:
            raise HTTPException(status_code=404, detail="Version B not found")

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
        ver_repo = VersionRepo(sb)
        version = ver_repo.get(version_id, owner_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

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

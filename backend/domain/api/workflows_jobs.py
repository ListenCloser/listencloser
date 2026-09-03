"""Workflow creation and durable Job control HTTP routes."""

from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth_utils import limiter, verify_token
from domain.api.dependencies import owner_id, supabase_client
from domain.api_schemas import WorkflowJobResponse
from domain.models import ArtifactKind, Capability, Job, JobStage, Version, Workflow, WorkflowKind
from domain.repositories import ArtifactRepo, JobRepo, VersionRepo, WorkflowRepo, WorkRepo

router = APIRouter()
_PUBLIC_CREATE_WORKFLOW_ACTIONS = frozenset({"perceptual_series", "transform"})


class UnderstandWorkflowBody(BaseModel):
    version_id: str
    project_id: str
    transcription_profile: Literal["auto", "solo_piano"] | None = None
    score_engine: Literal["musescore", "pm2s"] | None = None


class ScoreWorkflowBody(BaseModel):
    performance_midi_version_id: str
    project_id: str
    score_engine: Literal["musescore", "pm2s"] | None = None


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


def _canonical_transcription_profile(profile: str | None) -> str:
    """Normalize omitted transcription selection to the general Auto profile."""
    return profile or "auto"


def _canonical_score_engine(engine: str | None) -> str:
    """Normalize omitted Score selection to the current MuseScore baseline."""
    return engine or "musescore"


def _require_public_create_action(action: str) -> str:
    """Keep public workflow dispatch independent from worker registration."""
    if action not in _PUBLIC_CREATE_WORKFLOW_ACTIONS:
        raise HTTPException(status_code=400, detail="Unsupported workflow action")
    return action


def _require_version_in_project(
    sb,
    version_id: UUID,
    project_id: UUID,
    owner: str,
) -> Version:
    """Verify both ownership and project membership before queuing work."""
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


@router.post("/workflows/understand", response_model=WorkflowJobResponse)
@limiter.limit("10/minute")
async def create_understand_workflow(
    body: UnderstandWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        version = _require_version_in_project(sb, version_id, project_id, owner)
        profile = _canonical_transcription_profile(body.transcription_profile)
        score_engine = _canonical_score_engine(body.score_engine)

        job_id = uuid5(
            NAMESPACE_URL,
            f"hello-ai:understand:1.0:{owner}:{version_id}:{profile}:{score_engine}",
        )
        job_repo = JobRepo(sb)
        existing_job = job_repo.get(job_id, owner)
        if existing_job:
            existing_workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner)
            if not existing_workflow:
                raise RuntimeError("idempotent job references a missing workflow")
            return {"workflow": existing_workflow, "job": existing_job}

        workflow_repo = WorkflowRepo(sb)
        workflow = Workflow(
            id=uuid5(
                NAMESPACE_URL,
                f"hello-ai:understand-workflow:1.0:{owner}:{version_id}:{profile}:{score_engine}",
            ),
            project_id=project_id,
            kind=WorkflowKind.understand,
            target_version_id=version_id,
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
            capability=Capability(name="understand", version="1.0"),
            input_version_ids=[version_id],
            parameters={
                "fmt": Path(version.label).suffix.lstrip(".").lower() or "wav",
                "transcription_profile": profile,
                "score_engine": score_engine,
            },
            cache_key=f"understand:1.0:{owner}:{version_id}:{profile}:{score_engine}",
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
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/workflows/score", response_model=WorkflowJobResponse)
@limiter.limit("10/minute")
async def create_score_workflow(
    body: ScoreWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Rebuild Score from an existing canonical performance-MIDI version."""
    sb = supabase_client()
    owner = owner_id(auth)
    version_id = UUID(body.performance_midi_version_id)
    project_id = UUID(body.project_id)

    try:
        version = _require_version_in_project(sb, version_id, project_id, owner)
        artifact = ArtifactRepo(sb).get(version.artifact_id, owner)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        if artifact.kind != ArtifactKind.midi_performance:
            raise HTTPException(
                status_code=400,
                detail="Score rebuild requires a performance MIDI version",
            )

        score_engine = _canonical_score_engine(body.score_engine)
        job_id = uuid5(
            NAMESPACE_URL,
            f"listencloser:score:1.0:{owner}:{version_id}:{score_engine}",
        )
        job_repo = JobRepo(sb)
        existing_job = job_repo.get(job_id, owner)
        if existing_job:
            existing_workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner)
            if not existing_workflow:
                raise RuntimeError("idempotent score job references a missing workflow")
            return {"workflow": existing_workflow, "job": existing_job}

        workflow_repo = WorkflowRepo(sb)
        workflow = Workflow(
            id=uuid5(
                NAMESPACE_URL,
                f"listencloser:score-workflow:1.0:{owner}:{version_id}:{score_engine}",
            ),
            project_id=project_id,
            kind=WorkflowKind.understand,
            target_version_id=version_id,
            parameters={"score_engine": score_engine, "workflow_scope": "score_rebuild"},
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
            capability=Capability(name="score", version="1.0"),
            input_version_ids=[version_id],
            parameters={
                "score_engine": score_engine,
                "input_representation": "performance_midi",
            },
            cache_key=f"score:1.0:{owner}:{version_id}:{score_engine}",
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
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/jobs/{job_id}", response_model=JobStateResponse)
async def get_job(
    job_id: UUID,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)

    try:
        job = JobRepo(sb).get(job_id, owner)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return _job_state(job)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/jobs/{job_id}/cancel", response_model=JobStateResponse)
@limiter.limit("20/minute")
async def cancel_job(
    job_id: UUID,
    request: Request,
    auth=Depends(verify_token),
):
    try:
        return _job_state(JobRepo(supabase_client()).cancel(job_id, owner_id(auth)))
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
        return _job_state(JobRepo(supabase_client()).retry(job_id, owner_id(auth)))
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/workflows/analyze", response_model=WorkflowJobResponse)
@limiter.limit("10/minute")
async def create_analyze_workflow(
    body: AnalyzeWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        _require_version_in_project(sb, version_id, project_id, owner)

        workflow_repo = WorkflowRepo(sb)
        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.understand,
            target_version_id=version_id,
        )
        workflow = workflow_repo.create(workflow, owner)

        job = Job(
            workflow_id=workflow.id,
            capability=Capability(name="analyze", version="1.0"),
            input_version_ids=[version_id],
            created_by=owner,
        )
        job = JobRepo(sb).create(job, owner)

        return {"workflow": workflow, "job": job}

    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/workflows/correct", response_model=WorkflowJobResponse)
@limiter.limit("10/minute")
async def create_correct_workflow(
    body: CorrectWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        _require_version_in_project(sb, version_id, project_id, owner)

        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.correct,
            target_version_id=version_id,
        )
        workflow = WorkflowRepo(sb).create(workflow, owner)

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
            created_by=owner,
        )
        job = JobRepo(sb).create(job, owner)

        return {"workflow": workflow, "job": job}

    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/workflows/compare", response_model=WorkflowJobResponse)
@limiter.limit("10/minute")
async def create_compare_workflow(
    body: CompareWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)
    version_id_a = UUID(body.version_id_a)
    version_id_b = UUID(body.version_id_b)
    project_id = UUID(body.project_id)

    try:
        _require_version_in_project(sb, version_id_a, project_id, owner)
        _require_version_in_project(sb, version_id_b, project_id, owner)

        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.compare,
            target_version_id=version_id_a,
            parameters={"version_id_b": body.version_id_b},
        )
        workflow = WorkflowRepo(sb).create(workflow, owner)

        job = Job(
            workflow_id=workflow.id,
            capability=Capability(name="compare", version="1.0"),
            input_version_ids=[version_id_a, version_id_b],
            created_by=owner,
        )
        job = JobRepo(sb).create(job, owner)

        return {"workflow": workflow, "job": job}

    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/workflows/variation", response_model=WorkflowJobResponse)
@limiter.limit("5/minute")
async def create_variation_workflow(
    body: VariationWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Queue an idempotent, complete transposed take from a MIDI version."""
    sb = supabase_client()
    owner = owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        _require_version_in_project(sb, version_id, project_id, owner)
        job_id = uuid5(
            NAMESPACE_URL,
            f"hello-ai:variation:1.0:{owner}:{version_id}:{body.transpose_semitones}",
        )
        job_repo = JobRepo(sb)
        existing_job = job_repo.get(job_id, owner)
        if existing_job:
            workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner)
            if not workflow:
                raise RuntimeError("idempotent job references a missing workflow")
            return {"workflow": workflow, "job": existing_job}

        workflow = Workflow(
            id=uuid5(
                NAMESPACE_URL,
                (
                    "hello-ai:variation-workflow:1.0:"
                    f"{owner}:{version_id}:{body.transpose_semitones}"
                ),
            ),
            project_id=project_id,
            kind=WorkflowKind.create,
            target_version_id=version_id,
            parameters={"operation": "transpose", "semitones": body.transpose_semitones},
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
            capability=Capability(name="variation", version="1.0"),
            input_version_ids=[version_id],
            parameters={"transpose_semitones": body.transpose_semitones},
            cache_key=f"variation:1.0:{owner}:{version_id}:{body.transpose_semitones}",
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


@router.post("/workflows/create", response_model=WorkflowJobResponse)
@limiter.limit("5/minute")
async def create_create_workflow(
    body: CreateWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)
    version_id = UUID(body.version_id)
    project_id = UUID(body.project_id)

    try:
        capability_name = _require_public_create_action(body.action)
        _require_version_in_project(sb, version_id, project_id, owner)

        workflow = Workflow(
            project_id=project_id,
            kind=WorkflowKind.create,
            target_version_id=version_id,
            parameters={"action": capability_name, **body.parameters},
        )
        workflow = WorkflowRepo(sb).create(workflow, owner)

        job = Job(
            workflow_id=workflow.id,
            capability=Capability(name=capability_name, version="1.0"),
            input_version_ids=[version_id],
            parameters=body.parameters,
            created_by=owner,
        )
        job = JobRepo(sb).create(job, owner)

        return {"workflow": workflow, "job": job}

    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

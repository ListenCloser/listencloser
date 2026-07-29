"""
FastAPI router — domain model API endpoints for the understand workflow slice.
"""
import logging
import mimetypes
import os
import tempfile
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
    EntityKind,
    Insight,
    Job,
    NoteEntity,
    Project,
    Span,
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

logger = logging.getLogger("domain.api")

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
# POST /versions/{version_id}/transcribe
# ---------------------------------------------------------------------------


@router.post("/versions/{version_id}/transcribe")
@limiter.limit("10/minute")
async def transcribe_version(
    version_id: UUID,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)

    try:
        ver_repo = VersionRepo(sb)
        version = ver_repo.get(version_id, owner_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

        audio_bytes = sb.storage.from_(version.storage_bucket).download(
            version.storage_key
        )
        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Failed to download audio from storage")

        fmt = version.storage_key.rsplit(".", 1)[-1] if "." in version.storage_key else "wav"

        from music_features import transcribe_audio, enhance_audio

        try:
            enhanced = enhance_audio(audio_bytes, fmt=fmt)
            audio_bytes = enhanced
        except Exception as exc:
            logger.warning("enhance_audio failed, using raw bytes: %s", exc)

        result = transcribe_audio(audio_bytes, fmt="wav")

        artifact_resp = (
            sb.table("artifacts")
            .select("work_id")
            .eq("id", str(version.artifact_id))
            .execute()
        )
        if not artifact_resp.data:
            raise HTTPException(status_code=404, detail="Artifact not found")
        work_id = UUID(artifact_resp.data[0]["work_id"])

        midi_key = f"transcriptions/{version_id}/transcribed.mid"
        sb.storage.from_(version.storage_bucket).upload(
            midi_key, result["midi"], {"content-type": "audio/midi"}
        )

        art_repo = ArtifactRepo(sb)
        midi_artifact = art_repo.create(
            Artifact(
                work_id=work_id,
                kind=ArtifactKind.midi_performance,
                mime_type="audio/midi",
            ),
            owner_id,
        )
        midi_version = ver_repo.create(
            Version(
                artifact_id=midi_artifact.id,
                parent_version_id=version.id,
                lineage=[version.id],
                storage_key=midi_key,
                storage_bucket=version.storage_bucket,
                byte_size=len(result["midi"]),
                created_by=owner_id,
                label=f"Transcribed MIDI ({version.label or 'untitled'})",
            ),
            owner_id,
        )

        entity_repo = EntityRepo(sb)
        entity_ids: list[str] = []
        for note in result["notes"]:
            entity = entity_repo.create(
                Entity(
                    version_id=midi_version.id,
                    kind=EntityKind.note,
                    span=Span(
                        start_seconds=note["start"],
                        end_seconds=note["end"],
                    ),
                    note=NoteEntity(
                        pitch=note["pitch"],
                        start_seconds=note["start"],
                        end_seconds=note["end"],
                        velocity=note["velocity"],
                    ),
                ),
                owner_id,
            )
            entity_ids.append(str(entity.id))

        return {
            "notes": result["notes"],
            "num_notes": result["num_notes"],
            "midi_version_id": str(midi_version.id),
            "entity_ids": entity_ids,
        }

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# POST /versions/{version_id}/analyze
# ---------------------------------------------------------------------------


@router.post("/versions/{version_id}/analyze")
@limiter.limit("10/minute")
async def analyze_version(
    version_id: UUID,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)

    try:
        ver_repo = VersionRepo(sb)
        version = ver_repo.get(version_id, owner_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

        midi_bytes = sb.storage.from_(version.storage_bucket).download(
            version.storage_key
        )
        if not midi_bytes:
            raise HTTPException(status_code=500, detail="Failed to download MIDI from storage")

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(midi_bytes)
            midi_path = f.name

        from analyze import analyze_midi

        try:
            analysis = analyze_midi(midi_path)
        finally:
            os.unlink(midi_path)

        insight_repo = InsightRepo(sb)
        insight_ids: list[str] = []

        key_data = analysis.get("key", {}) or {}
        if key_data:
            tonic = key_data.get("tonic", "?")
            mode = key_data.get("mode", "?")
            key_conf = float(key_data.get("confidence", 0.0))
            kid = insight_repo.create(
                Insight(
                    version_id=version_id,
                    kind="key",
                    claim=f"Key: {tonic} {mode}",
                    evidence={"tonic": tonic, "mode": mode},
                    confidence=key_conf,
                    provenance={
                        "capability": "analyze",
                        "capability_version": "1.0",
                    },
                    created_by=owner_id,
                ),
                owner_id,
            )
            insight_ids.append(str(kid))

        tempo_data = analysis.get("tempo", {}) or {}
        if tempo_data:
            bpm = float(tempo_data.get("bpm", 0))
            tempo_conf = float(tempo_data.get("confidence", 0.0))
            tid = insight_repo.create(
                Insight(
                    version_id=version_id,
                    kind="tempo",
                    claim=f"Tempo: {bpm} BPM",
                    evidence={"bpm": bpm},
                    confidence=tempo_conf,
                    provenance={
                        "capability": "analyze",
                        "capability_version": "1.0",
                    },
                    created_by=owner_id,
                ),
                owner_id,
            )
            insight_ids.append(str(tid))

        ts_data = analysis.get("time_signature", {}) or {}
        if ts_data:
            num = int(ts_data.get("numerator", 4))
            den = int(ts_data.get("denominator", 4))
            ts_conf = float(ts_data.get("confidence", 0.0))
            tsid = insight_repo.create(
                Insight(
                    version_id=version_id,
                    kind="time_signature",
                    claim=f"Time Signature: {num}/{den}",
                    evidence={"numerator": num, "denominator": den},
                    confidence=ts_conf,
                    provenance={
                        "capability": "analyze",
                        "capability_version": "1.0",
                    },
                    created_by=owner_id,
                ),
                owner_id,
            )
            insight_ids.append(str(tsid))

        chords = analysis.get("chords", []) or []
        for ch in chords:
            root = ch.get("root", "?")
            quality = ch.get("quality", "?")
            start = float(ch.get("start", 0))
            end = float(ch.get("end", 0))
            cid = insight_repo.create(
                Insight(
                    version_id=version_id,
                    kind="chord",
                    claim=f"{root}:{quality}",
                    evidence=ch,
                    span=Span(start_seconds=start, end_seconds=end),
                    confidence=0.85,
                    provenance={
                        "capability": "analyze",
                        "capability_version": "1.0",
                    },
                    created_by=owner_id,
                ),
                owner_id,
            )
            insight_ids.append(str(cid))

        rns = analysis.get("roman_numerals", []) or []
        for rn in rns:
            figure = rn.get("figure", "?")
            start = float(rn.get("start", 0))
            end = float(rn.get("end", 0))
            rid = insight_repo.create(
                Insight(
                    version_id=version_id,
                    kind="roman_numeral",
                    claim=figure,
                    evidence=rn,
                    span=Span(start_seconds=start, end_seconds=end),
                    confidence=0.8,
                    provenance={
                        "capability": "analyze",
                        "capability_version": "1.0",
                    },
                    created_by=owner_id,
                ),
                owner_id,
            )
            insight_ids.append(str(rid))

        cadences = analysis.get("cadences", []) or []
        for cad in cadences:
            cad_type = cad.get("type", "?")
            chords_str = " -> ".join(cad.get("chords", []))
            position = float(cad.get("position", 0))
            caid = insight_repo.create(
                Insight(
                    version_id=version_id,
                    kind="cadence",
                    claim=f"{cad_type}: {chords_str}",
                    evidence=cad,
                    span=Span(start_seconds=position),
                    confidence=0.8,
                    provenance={
                        "capability": "analyze",
                        "capability_version": "1.0",
                    },
                    created_by=owner_id,
                ),
                owner_id,
            )
            insight_ids.append(str(caid))

        return {
            "analysis": analysis,
            "insight_ids": insight_ids,
        }

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

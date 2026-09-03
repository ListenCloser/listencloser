"""Artifact upload and immutable Version resource HTTP routes."""

import logging
import mimetypes
import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from auth_utils import limiter, verify_token
from domain.api.dependencies import owner_id, supabase_client
from domain.api.storage import signed_url
from domain.api_schemas import UploadArtifactResponse, VersionResourceResponse
from domain.models import Artifact, ArtifactKind, Version, Work
from domain.repositories import ArtifactRepo, ProjectRepo, VersionRepo, WorkRepo
from domain.storage_locator_policy import classify_version_storage_locator
from domain.work_bundle_repository import WorkBundleRepository

router = APIRouter()
logger = logging.getLogger("domain.api")

_ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "m4a", "flac", "ogg", "aac"}


@router.post("/projects/{project_id}/artifacts/upload", response_model=UploadArtifactResponse)
@limiter.limit("10/minute")
async def upload_artifact(
    project_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    work_id: str | None = Form(None),
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)

    try:
        project = ProjectRepo(sb).get(project_id, owner)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        filename = file.filename or "untitled"
        ext = Path(filename).suffix.lstrip(".").lower()
        if ext not in _ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Unsupported audio format")

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
            work_uuid = UUID(work_id)
            work = work_repo.get(work_uuid, owner)
            if not work:
                raise HTTPException(status_code=404, detail="Work not found")
            if work.project_id != project_id:
                raise HTTPException(
                    status_code=400,
                    detail="Work does not belong to this project",
                )
        else:
            work = Work(project_id=project_id, title=Path(filename).stem)
            work = work_repo.create(work, owner)
            created_work = True

        artifact_draft = Artifact(
            work_id=work.id,
            kind=ArtifactKind.audio_original,
            mime_type=mime_type,
        )
        artifact_repo = ArtifactRepo(sb)
        artifact = None
        storage_key = None
        bucket = "artifacts"
        try:
            artifact = artifact_repo.create(artifact_draft, owner)
            storage_key = f"{owner}/{project_id}/{artifact.id}/{uuid4().hex}.{ext}"
            sb.storage.from_(bucket).upload(storage_key, raw, {"content-type": mime_type})

            version = Version(
                artifact_id=artifact.id,
                storage_key=storage_key,
                storage_bucket=bucket,
                byte_size=len(raw),
                created_by=owner,
                label=filename,
            )
            version = VersionRepo(sb).create(version, owner)
        except Exception:
            logger.exception("upload_finalize_failed", extra={"project_id": str(project_id)})
            if storage_key:
                try:
                    sb.storage.from_(bucket).remove([storage_key])
                except Exception:
                    logger.exception("upload_storage_cleanup_failed")
            if artifact:
                try:
                    artifact_repo.delete(artifact.id, owner)
                except Exception:
                    logger.exception("upload_artifact_cleanup_failed")
            if created_work:
                try:
                    work_repo.delete(work.id, owner)
                except Exception:
                    logger.exception("upload_work_cleanup_failed")
            raise

        return {"artifact": artifact, "version": version}

    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/versions/{version_id}", response_model=VersionResourceResponse)
async def get_version_resource(
    version_id: UUID,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)

    try:
        version = VersionRepo(sb).get(version_id, owner)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        artifact = ArtifactRepo(sb).get(version.artifact_id, owner)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        snapshot = WorkBundleRepository(sb).load(artifact.work_id, owner)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Work not found")
        decision = classify_version_storage_locator(
            version,
            owner_id=owner,
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
            "signed_url": signed_url(response),
        }
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

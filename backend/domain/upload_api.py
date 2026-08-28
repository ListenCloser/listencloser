"""Direct-to-Storage artifact upload lifecycle.

Large request bodies should not be relayed through Vercel and the Oracle API.
The API authorizes a short-lived, owner-scoped Storage path, the browser sends
bytes directly to private Supabase Storage, and the API then finalizes the
canonical Work/Artifact/Version metadata graph.
"""

import mimetypes
import os
import re
from contextlib import suppress
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth_utils import limiter, verify_token
from domain.api_schemas import UploadArtifactResponse
from domain.models import Artifact, ArtifactKind, Version, Work
from domain.repositories import ArtifactRepo, ProjectRepo, VersionRepo, WorkRepo, get_supabase

router = APIRouter(prefix="/api/v1")

_STORAGE_BUCKET = "artifacts"
_PENDING_SEGMENT = "pending"
_ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "m4a", "flac", "ogg", "aac"}
_PENDING_BASENAME = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]+$")
_DEFAULT_MAX_UPLOAD_BYTES = 4 * 1024 * 1024


class CreateUploadIntentBody(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    byte_size: int = Field(gt=0)
    content_type: str | None = Field(default=None, max_length=255)
    work_id: UUID | None = None


class UploadIntentResponse(BaseModel):
    bucket: str
    storage_key: str
    token: str
    max_bytes: int


class FinalizeUploadBody(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    byte_size: int = Field(gt=0)
    content_type: str | None = Field(default=None, max_length=255)
    storage_key: str = Field(min_length=1, max_length=1024)
    work_id: UUID | None = None


def _owner_id(auth) -> str:
    return str(auth.user.id)


def _sb():
    client = get_supabase()
    if not client:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return client


def _max_upload_bytes() -> int:
    try:
        value = int(os.environ.get("MAX_UPLOAD_BYTES", str(_DEFAULT_MAX_UPLOAD_BYTES)))
    except ValueError as exc:
        raise RuntimeError("MAX_UPLOAD_BYTES must be an integer") from exc
    if value <= 0:
        raise RuntimeError("MAX_UPLOAD_BYTES must be positive")
    return value


def _audio_descriptor(filename: str, byte_size: int, content_type: str | None) -> tuple[str, str]:
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename:
        raise HTTPException(status_code=400, detail="Filename must not contain a path")

    ext = Path(safe_name).suffix.lstrip(".").lower()
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported audio format")

    max_bytes = _max_upload_bytes()
    if byte_size > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds upload size limit")

    guessed = mimetypes.guess_type(safe_name)[0]
    mime_type = guessed or content_type or "application/octet-stream"
    return ext, mime_type


def _pending_storage_key(owner_id: str, project_id: UUID, ext: str) -> str:
    return f"{owner_id}/{project_id}/{_PENDING_SEGMENT}/{uuid4().hex}.{ext}"


def _validate_pending_storage_key(
    storage_key: str,
    owner_id: str,
    project_id: UUID,
    expected_ext: str,
) -> None:
    path = PurePosixPath(storage_key)
    parts = path.parts
    expected_prefix = (owner_id, str(project_id), _PENDING_SEGMENT)
    if len(parts) != 4 or tuple(parts[:3]) != expected_prefix:
        raise HTTPException(status_code=400, detail="Invalid upload storage key")
    if not _PENDING_BASENAME.fullmatch(parts[3]):
        raise HTTPException(status_code=400, detail="Invalid upload storage key")
    if Path(parts[3]).suffix.lstrip(".").lower() != expected_ext:
        raise HTTPException(status_code=400, detail="Upload format does not match storage key")


def _signed_upload_token(response) -> str:
    data = getattr(response, "data", None) or response
    if isinstance(data, dict):
        token = data.get("token") or data.get("signedToken") or data.get("signed_token")
    else:
        token = getattr(data, "token", None)
    if not token:
        raise RuntimeError("Storage provider did not return a signed upload token")
    return str(token)


def _require_project_and_work(sb, project_id: UUID, work_id: UUID | None, owner_id: str):
    project = ProjectRepo(sb).get(project_id, owner_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if work_id is None:
        return None
    work = WorkRepo(sb).get(work_id, owner_id)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    if work.project_id != project_id:
        raise HTTPException(status_code=400, detail="Work does not belong to this project")
    return work


def _find_storage_object(sb, storage_key: str) -> dict | None:
    path = PurePosixPath(storage_key)
    parent = str(path.parent)
    name = path.name
    rows = sb.storage.from_(_STORAGE_BUCKET).list(
        path=parent,
        options={"limit": 100, "search": name},
    )
    return next((row for row in (rows or []) if row.get("name") == name), None)


def _object_size(row: dict) -> int | None:
    metadata = row.get("metadata") or {}
    value = metadata.get("size") if isinstance(metadata, dict) else None
    if value is None:
        value = row.get("size")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _existing_upload(sb, storage_key: str, owner_id: str) -> tuple[Artifact, Version] | None:
    rows = (
        sb.table("artifact_versions")
        .select("id,artifact_id")
        .eq("storage_bucket", _STORAGE_BUCKET)
        .eq("storage_key", storage_key)
        .limit(1)
        .execute()
    )
    if not rows.data:
        return None
    version = VersionRepo(sb).get(UUID(rows.data[0]["id"]), owner_id)
    artifact = ArtifactRepo(sb).get(UUID(rows.data[0]["artifact_id"]), owner_id)
    if not version or not artifact:
        raise RuntimeError("Finalized upload references missing metadata")
    return artifact, version


@router.post(
    "/projects/{project_id}/artifacts/upload-intent",
    response_model=UploadIntentResponse,
)
@limiter.limit("10/minute")
async def create_upload_intent(
    project_id: UUID,
    body: CreateUploadIntentBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    _require_project_and_work(sb, project_id, body.work_id, owner_id)
    ext, _ = _audio_descriptor(body.filename, body.byte_size, body.content_type)
    storage_key = _pending_storage_key(owner_id, project_id, ext)

    try:
        response = sb.storage.from_(_STORAGE_BUCKET).create_signed_upload_url(storage_key)
        token = _signed_upload_token(response)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not authorize Storage upload") from exc

    return UploadIntentResponse(
        bucket=_STORAGE_BUCKET,
        storage_key=storage_key,
        token=token,
        max_bytes=_max_upload_bytes(),
    )


@router.post(
    "/projects/{project_id}/artifacts/finalize-upload",
    response_model=UploadArtifactResponse,
)
@limiter.limit("10/minute")
async def finalize_upload(
    project_id: UUID,
    body: FinalizeUploadBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = _sb()
    owner_id = _owner_id(auth)
    work = _require_project_and_work(sb, project_id, body.work_id, owner_id)
    ext, mime_type = _audio_descriptor(body.filename, body.byte_size, body.content_type)
    _validate_pending_storage_key(body.storage_key, owner_id, project_id, ext)

    existing = _existing_upload(sb, body.storage_key, owner_id)
    if existing:
        artifact, version = existing
        if body.work_id is not None and artifact.work_id != body.work_id:
            raise HTTPException(
                status_code=409,
                detail="Upload was already finalized for another work",
            )
        return UploadArtifactResponse(artifact=artifact, version=version)

    stored = _find_storage_object(sb, body.storage_key)
    if not stored:
        raise HTTPException(status_code=409, detail="Storage upload is not complete")
    stored_size = _object_size(stored)
    if stored_size is not None and stored_size != body.byte_size:
        raise HTTPException(status_code=409, detail="Uploaded file size does not match intent")

    work_repo = WorkRepo(sb)
    art_repo = ArtifactRepo(sb)
    created_work = False
    artifact = None
    try:
        if work is None:
            work = work_repo.create(
                Work(project_id=project_id, title=Path(body.filename).stem),
                owner_id,
            )
            created_work = True

        artifact = art_repo.create(
            Artifact(
                work_id=work.id,
                kind=ArtifactKind.audio_original,
                mime_type=mime_type,
            ),
            owner_id,
        )
        version = VersionRepo(sb).create(
            Version(
                artifact_id=artifact.id,
                storage_key=body.storage_key,
                storage_bucket=_STORAGE_BUCKET,
                byte_size=body.byte_size,
                created_by=owner_id,
                label=body.filename,
            ),
            owner_id,
        )
    except Exception:
        if artifact is not None:
            with suppress(Exception):
                art_repo.delete(artifact.id, owner_id)
        if created_work and work is not None:
            with suppress(Exception):
                work_repo.delete(work.id, owner_id)
        with suppress(Exception):
            sb.storage.from_(_STORAGE_BUCKET).remove([body.storage_key])
        raise

    return UploadArtifactResponse(artifact=artifact, version=version)

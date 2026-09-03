"""Project and Work lifecycle HTTP routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth_utils import limiter, verify_token
from domain.api.dependencies import owner_id, supabase_client
from domain.api.storage import signed_url
from domain.api_schemas import DeletedWorkResponse, WorkBundleResponse
from domain.models import Project, Work
from domain.repositories import ArtifactRepo, ProjectRepo, VersionRepo, WorkRepo
from domain.storage_locator_policy import classify_version_storage_locator
from domain.work_bundle_repository import WorkBundleRepository

router = APIRouter()
logger = logging.getLogger("domain.api")


class CreateProjectBody(BaseModel):
    name: str
    description: str = ""


class CreateWorkBody(BaseModel):
    title: str
    composer: str | None = None


@router.post("/projects", response_model=Project)
@limiter.limit("10/minute")
def create_project(
    body: CreateProjectBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)
    repo = ProjectRepo(sb)
    project = Project(owner_id=owner, name=body.name, description=body.description)
    try:
        return repo.create(project)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/projects", response_model=list[Project])
def list_projects(
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)
    return ProjectRepo(sb).list_by_owner(owner)


@router.post("/projects/{project_id}/works", response_model=Work)
@limiter.limit("10/minute")
def create_work(
    project_id: UUID,
    body: CreateWorkBody,
    request: Request,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)
    repo = WorkRepo(sb)
    work = Work(project_id=project_id, title=body.title, composer=body.composer)
    try:
        return repo.create(work, owner)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/projects/{project_id}/works", response_model=list[Work])
def list_works(
    project_id: UUID,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)
    try:
        return WorkRepo(sb).list_by_project(project_id, owner)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/works/{work_id}", response_model=WorkBundleResponse)
def get_work_bundle(
    work_id: UUID,
    auth=Depends(verify_token),
):
    """Return a work and its complete immutable artifact/version graph."""
    sb = supabase_client()
    owner = owner_id(auth)
    try:
        snapshot = WorkBundleRepository(sb).load(work_id, owner)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Work not found")
        allowed_job_ids = {job.id for job in snapshot.jobs}

        items = []
        for artifact in snapshot.artifacts:
            versions = snapshot.versions_by_artifact.get(artifact.id, [])
            latest = versions[0] if versions else None
            artifact_signed_url = None
            if latest:
                decision = classify_version_storage_locator(
                    latest,
                    owner_id=owner,
                    project_id=snapshot.work.project_id,
                    artifact_id=artifact.id,
                    allowed_job_ids=allowed_job_ids,
                )
                if decision.trusted:
                    try:
                        response = sb.storage.from_(latest.storage_bucket).create_signed_url(
                            latest.storage_key, 3600
                        )
                        artifact_signed_url = signed_url(response)
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
                    "signed_url": artifact_signed_url,
                }
            )
        return {"work": snapshot.work, "artifacts": items, "jobs": snapshot.jobs}
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/works/{work_id}", response_model=DeletedWorkResponse)
@limiter.limit("10/minute")
def delete_work(
    work_id: UUID,
    request: Request,
    auth=Depends(verify_token),
):
    """Delete a work and its artifacts, versions, and storage objects."""
    sb = supabase_client()
    owner = owner_id(auth)
    try:
        work_repo = WorkRepo(sb)
        work = work_repo.get(work_id, owner)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")
        snapshot = WorkBundleRepository(sb).load(work_id, owner)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Work not found")
        allowed_job_ids = {job.id for job in snapshot.jobs}

        artifact_repo = ArtifactRepo(sb)
        version_repo = VersionRepo(sb)
        artifacts = artifact_repo.list_by_work(work_id, owner)
        for artifact in artifacts:
            versions = version_repo.list_by_artifact(artifact.id, owner)
            for version in versions:
                decision = classify_version_storage_locator(
                    version,
                    owner_id=owner,
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
                artifact_repo.delete(artifact.id, owner)
            except Exception:
                logger.exception("artifact_delete_failed")

        work_repo.delete(work_id, owner)
        return {"deleted": str(work_id)}
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

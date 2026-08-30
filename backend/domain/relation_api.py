"""HTTP exposure for on-demand same-work perceptual span comparisons."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import verify_token
from domain.api_schemas import PerceptualSpanComparisonResponse
from domain.models import Version
from domain.relation_query import (
    PerceptualSpanComparisonQuery,
    compare_persisted_perceptual_spans,
)
from domain.repositories import get_supabase
from domain.storage_locator_policy import classify_version_storage_locator
from domain.work_bundle_repository import WorkBundleRepository, WorkBundleSnapshot

router = APIRouter(prefix="/api/v1")


class PerceptualSpanComparisonBody(BaseModel):
    """Compare two explicit seconds-authoritative spans in one audio Version."""

    source_version_id: UUID
    subject_start_seconds: float
    subject_end_seconds: float
    comparison_start_seconds: float
    comparison_end_seconds: float


def _owner_id(auth) -> str:
    return auth.user.id


def _source_version(
    snapshot: WorkBundleSnapshot,
    source_version_id: UUID,
) -> Version | None:
    return next(
        (
            version
            for versions in snapshot.versions_by_artifact.values()
            for version in versions
            if version.id == source_version_id
        ),
        None,
    )


def _authorized_report_loader(
    snapshot: WorkBundleSnapshot,
    sb,
    owner_id: str,
) -> Callable[[Version], bytes]:
    """Build a fail-closed report loader over one authorized Work snapshot."""

    artifact_ids = {artifact.id for artifact in snapshot.artifacts}
    version_ids_by_artifact = {
        artifact_id: {version.id for version in versions}
        for artifact_id, versions in snapshot.versions_by_artifact.items()
    }
    allowed_job_ids = {job.id for job in snapshot.jobs}

    def load_report(version: Version) -> bytes:
        authorized_version_ids = version_ids_by_artifact.get(version.artifact_id, set())
        if version.artifact_id not in artifact_ids or version.id not in authorized_version_ids:
            raise PermissionError("perceptual evidence report is not in the authorized Work snapshot")

        decision = classify_version_storage_locator(
            version,
            owner_id=owner_id,
            project_id=snapshot.work.project_id,
            artifact_id=version.artifact_id,
            allowed_job_ids=allowed_job_ids,
        )
        if not decision.trusted:
            raise PermissionError("perceptual evidence report storage locator is not authorized")

        return sb.storage.from_(version.storage_bucket).download(version.storage_key)

    return load_report


@router.post(
    "/works/{work_id}/relations/perceptual-span-comparison",
    response_model=PerceptualSpanComparisonResponse,
)
async def compare_perceptual_spans(
    work_id: UUID,
    body: PerceptualSpanComparisonBody,
    auth=Depends(verify_token),
):
    """Compare two user-selected spans using persisted, lineage-checked evidence."""

    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # WorkBundleRepository already uses the owned Work as its authorization
    # root and returns None when that Work is unavailable to this owner. Do not
    # reinterpret generic ValueError/validation failures as client-facing 404s:
    # descendant model-validation or repository bugs are internal failures and
    # must reach the normal server-error boundary without leaking their detail.
    owner_id = _owner_id(auth)
    snapshot = WorkBundleRepository(sb).load(work_id, owner_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Work not found")

    source_version = _source_version(snapshot, body.source_version_id)
    if source_version is None:
        raise HTTPException(status_code=404, detail="Source version not found in work")

    result = compare_persisted_perceptual_spans(
        snapshot,
        source_version=source_version,
        query=PerceptualSpanComparisonQuery(
            subject_start_seconds=body.subject_start_seconds,
            subject_end_seconds=body.subject_end_seconds,
            comparison_start_seconds=body.comparison_start_seconds,
            comparison_end_seconds=body.comparison_end_seconds,
        ),
        load_report=_authorized_report_loader(snapshot, sb, owner_id),
    )
    return PerceptualSpanComparisonResponse.model_validate(result.model_dump())

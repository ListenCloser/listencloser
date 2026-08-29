"""HTTP exposure for on-demand same-work perceptual span comparisons."""

from __future__ import annotations

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

    try:
        snapshot = WorkBundleRepository(sb).load(work_id, _owner_id(auth))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
        load_report=lambda version: sb.storage.from_(version.storage_bucket).download(
            version.storage_key
        ),
    )
    return PerceptualSpanComparisonResponse.model_validate(result.model_dump())

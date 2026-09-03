"""Persisted evidence read HTTP routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from auth_utils import verify_token
from domain.api.dependencies import owner_id, supabase_client
from domain.capability_policy import is_exposed
from domain.models import Entity, Insight
from domain.repositories import EntityRepo, InsightRepo

router = APIRouter()
logger = logging.getLogger("domain.api")


def _inspector_exposed(insight) -> bool:
    """Return whether a persisted Insight is safe to expose in the Inspector."""
    kind = getattr(insight, "kind", None)
    if not isinstance(kind, str) or not kind:
        return False
    try:
        return is_exposed(kind, "inspector")
    except KeyError:
        logger.warning("unregistered_insight_hidden", extra={"kind": kind})
        return False


@router.get("/versions/{version_id}/entities", response_model=list[Entity])
def list_entities(
    version_id: UUID,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)

    try:
        return EntityRepo(sb).list_by_version(version_id, owner)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/versions/{version_id}/insights", response_model=list[Insight])
def list_insights(
    version_id: UUID,
    auth=Depends(verify_token),
):
    sb = supabase_client()
    owner = owner_id(auth)

    try:
        all_insights = InsightRepo(sb).list_by_version(version_id, owner)
        return [item for item in all_insights if _inspector_exposed(item)]
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

"""Composition-only router for the domain HTTP API."""

from fastapi import APIRouter

from domain.api.artifacts_versions import router as artifacts_versions_router
from domain.api.evidence import router as evidence_router
from domain.api.pitch_contour import router as pitch_contour_router
from domain.api.projects_works import router as projects_works_router
from domain.api.workflows_jobs import router as workflows_jobs_router

router = APIRouter(prefix="/api/v1")
router.include_router(projects_works_router)
router.include_router(artifacts_versions_router)
router.include_router(evidence_router)
router.include_router(workflows_jobs_router)
router.include_router(pitch_contour_router)

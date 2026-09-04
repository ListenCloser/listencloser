"""On-demand Similar moments query over one authorized perceptual report.

The immutable ``perceptual_series`` report remains source of truth. Similar
moment candidates are cheap deterministic experimental derivations and are not
persisted as a second evidence stream.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from domain.models import Version
from domain.perceptual_report import PerceptualEvidenceReport
from domain.relation_query import (
    _matching_report_versions,
    _source_artifact,
    _validate_report_lineage,
    _validate_report_payload,
)
from domain.similar_moments import SimilarMomentsObservation, find_similar_moments
from domain.work_bundle_repository import WorkBundleSnapshot

SimilarMomentsStatus = Literal["supported", "unavailable", "withheld", "failed"]


class SimilarMomentsQuery(BaseModel):
    """One exact selected passage whose same-Work neighbors should be proposed."""

    model_config = ConfigDict(frozen=True)

    query_start_seconds: float
    query_end_seconds: float
    max_matches: int = Field(default=3, ge=1, le=5)


class SimilarMomentsQueryResult(BaseModel):
    """Truthful availability/result state for experimental Similar moments."""

    model_config = ConfigDict(frozen=True)

    status: SimilarMomentsStatus
    evidence_report_version_id: UUID | None = None
    observation: SimilarMomentsObservation | None = None
    reasons: list[str] = Field(default_factory=list)


def _result(
    status: SimilarMomentsStatus,
    *,
    evidence_report_version_id: UUID | None = None,
    observation: SimilarMomentsObservation | None = None,
    reasons: list[str] | None = None,
) -> SimilarMomentsQueryResult:
    return SimilarMomentsQueryResult(
        status=status,
        evidence_report_version_id=evidence_report_version_id,
        observation=observation,
        reasons=list(reasons or []),
    )


def find_persisted_similar_moments(
    snapshot: WorkBundleSnapshot,
    *,
    source_version: Version,
    query: SimilarMomentsQuery,
    load_report: Callable[[Version], bytes],
) -> SimilarMomentsQueryResult:
    """Resolve exact promoted evidence, then propose bounded same-Work candidates."""

    source_artifact, source_reasons = _source_artifact(snapshot, source_version)
    if source_artifact is None:
        return _result("failed", reasons=source_reasons)

    report_versions = _matching_report_versions(snapshot, source_version.id)
    if not report_versions:
        return _result(
            "unavailable",
            reasons=["perceptual evidence is not available for this source Version"],
        )

    report_version = report_versions[0]
    lineage_reasons = _validate_report_lineage(report_version, source_version, source_artifact)
    if lineage_reasons:
        return _result(
            "failed",
            evidence_report_version_id=report_version.id,
            reasons=lineage_reasons,
        )

    try:
        report_bytes = load_report(report_version)
    except Exception:
        return _result(
            "failed",
            evidence_report_version_id=report_version.id,
            reasons=["perceptual evidence report could not be loaded"],
        )

    try:
        report = PerceptualEvidenceReport.model_validate_json(report_bytes)
    except (ValidationError, ValueError, TypeError):
        return _result(
            "failed",
            evidence_report_version_id=report_version.id,
            reasons=["perceptual evidence report could not be validated"],
        )

    payload_reasons = _validate_report_payload(report, report_version, source_version)
    if payload_reasons:
        return _result(
            "failed",
            evidence_report_version_id=report_version.id,
            reasons=payload_reasons,
        )

    try:
        observation = find_similar_moments(
            report,
            evidence_report_version_id=report_version.id,
            query_start_seconds=query.query_start_seconds,
            query_end_seconds=query.query_end_seconds,
            max_matches=query.max_matches,
        )
    except ValueError as exc:
        return _result(
            "withheld",
            evidence_report_version_id=report_version.id,
            reasons=[str(exc)],
        )

    return _result(
        "supported",
        evidence_report_version_id=report_version.id,
        observation=observation,
    )


__all__ = [
    "SimilarMomentsQuery",
    "SimilarMomentsQueryResult",
    "SimilarMomentsStatus",
    "find_persisted_similar_moments",
]

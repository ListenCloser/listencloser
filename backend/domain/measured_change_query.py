"""On-demand measured-change query over one authorized perceptual report.

The immutable ``perceptual_series`` report remains source of truth. Change
candidates are cheap deterministic experimental derivations and are not
persisted as a second evidence stream.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from domain.measured_changes import MeasuredChangeCandidate, discover_measured_changes
from domain.models import Version
from domain.perceptual_report import PerceptualEvidenceReport
from domain.relation_query import (
    _matching_report_versions,
    _source_artifact,
    _validate_report_lineage,
    _validate_report_payload,
)
from domain.work_bundle_repository import WorkBundleSnapshot

MeasuredChangeStatus = Literal["supported", "unavailable", "withheld", "failed"]


class MeasuredChangeQueryResult(BaseModel):
    """Truthful availability/result state for experimental measured changes."""

    model_config = ConfigDict(frozen=True)

    status: MeasuredChangeStatus
    evidence_report_version_id: UUID | None = None
    method: str | None = None
    method_parameters: dict[str, float | int] = Field(default_factory=dict)
    candidates: list[MeasuredChangeCandidate] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


def _result(
    status: MeasuredChangeStatus,
    *,
    evidence_report_version_id: UUID | None = None,
    method: str | None = None,
    method_parameters: dict[str, float | int] | None = None,
    candidates: list[MeasuredChangeCandidate] | None = None,
    reasons: list[str] | None = None,
) -> MeasuredChangeQueryResult:
    return MeasuredChangeQueryResult(
        status=status,
        evidence_report_version_id=evidence_report_version_id,
        method=method,
        method_parameters=dict(method_parameters or {}),
        candidates=list(candidates or []),
        reasons=list(reasons or []),
    )


def discover_persisted_measured_changes(
    snapshot: WorkBundleSnapshot,
    *,
    source_version: Version,
    load_report: Callable[[Version], bytes],
) -> MeasuredChangeQueryResult:
    """Resolve exact promoted evidence and derive a bounded experimental top set."""

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

    discovery = discover_measured_changes(
        report,
        evidence_report_version_id=report_version.id,
    )
    if discovery.status == "withheld":
        return _result(
            "withheld",
            evidence_report_version_id=report_version.id,
            method=discovery.method,
            method_parameters=discovery.method_parameters,
            reasons=discovery.reasons,
        )

    return _result(
        "supported",
        evidence_report_version_id=report_version.id,
        method=discovery.method,
        method_parameters=discovery.method_parameters,
        candidates=discovery.candidates,
    )


__all__ = [
    "MeasuredChangeQueryResult",
    "MeasuredChangeStatus",
    "discover_persisted_measured_changes",
]

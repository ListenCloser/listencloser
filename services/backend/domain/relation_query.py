"""On-demand query boundary for same-work perceptual span comparisons.

The persisted source of truth remains the immutable ``perceptual_series`` analysis
report. User-selected A/B comparisons are cheap deterministic derivations over
that report, so this module resolves and validates the latest matching report,
then composes a grounded relation finding without persisting duplicate relation
state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from domain.models import Artifact, ArtifactKind, Version
from domain.perceptual_report import PerceptualEvidenceReport
from domain.relation_findings import (
    GroundedRelationFinding,
    compose_grounded_relation_finding,
)
from domain.relation_observations import SecondsSpanLocator, compare_perceptual_spans
from domain.work_bundle_repository import WorkBundleSnapshot

ComparisonStatus = Literal["supported", "unavailable", "withheld", "failed"]
_ALLOWED_SOURCE_KINDS = {
    ArtifactKind.audio_original,
    ArtifactKind.audio_enhanced,
    ArtifactKind.audio_rendered,
}


class PerceptualSpanComparisonQuery(BaseModel):
    """Two explicit seconds-authoritative spans over one source Version."""

    model_config = ConfigDict(frozen=True)

    subject_start_seconds: float
    subject_end_seconds: float
    comparison_start_seconds: float
    comparison_end_seconds: float


class PerceptualSpanComparisonQueryResult(BaseModel):
    """Truthful availability/result state for an on-demand relation query."""

    model_config = ConfigDict(frozen=True)

    status: ComparisonStatus
    evidence_report_version_id: UUID | None = None
    finding: GroundedRelationFinding | None = None
    reasons: list[str] = Field(default_factory=list)


def _result(
    status: ComparisonStatus,
    *,
    evidence_report_version_id: UUID | None = None,
    finding: GroundedRelationFinding | None = None,
    reasons: list[str] | None = None,
) -> PerceptualSpanComparisonQueryResult:
    return PerceptualSpanComparisonQueryResult(
        status=status,
        evidence_report_version_id=evidence_report_version_id,
        finding=finding,
        reasons=list(reasons or []),
    )


def _source_artifact(
    snapshot: WorkBundleSnapshot,
    source_version: Version,
) -> tuple[Artifact | None, list[str]]:
    artifact = next(
        (item for item in snapshot.artifacts if item.id == source_version.artifact_id),
        None,
    )
    if artifact is None:
        return None, ["source Version is not part of the authorized Work snapshot"]
    if source_version.id not in {
        item.id for item in snapshot.versions_by_artifact.get(artifact.id, [])
    }:
        return None, ["source Version is not part of the authorized Work snapshot"]
    if artifact.kind not in _ALLOWED_SOURCE_KINDS:
        return None, ["perceptual span comparison requires an audio source Version"]
    return artifact, []


def _metadata_source_version_id(version: Version) -> UUID | None:
    raw = version.metadata.get("source_version_id")
    if raw is None:
        return None
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def _matching_report_versions(
    snapshot: WorkBundleSnapshot,
    source_version_id: UUID,
) -> list[Version]:
    candidates: list[Version] = []
    for artifact in snapshot.artifacts:
        if artifact.kind != ArtifactKind.analysis_report:
            continue
        for version in snapshot.versions_by_artifact.get(artifact.id, []):
            if version.metadata.get("report_type") != "perceptual_series":
                continue
            if _metadata_source_version_id(version) != source_version_id:
                continue
            candidates.append(version)
    return sorted(
        candidates,
        key=lambda version: (version.created_at, str(version.id)),
        reverse=True,
    )


def _validate_report_lineage(
    report_version: Version,
    source_version: Version,
    source_artifact: Artifact,
) -> list[str]:
    reasons: list[str] = []
    if report_version.parent_version_id != source_version.id:
        reasons.append("perceptual evidence report parent does not match the source Version")
    if source_version.id not in report_version.lineage:
        reasons.append("perceptual evidence report lineage does not include the source Version")

    raw_source_artifact_id = report_version.metadata.get("source_artifact_id")
    try:
        metadata_source_artifact_id = UUID(str(raw_source_artifact_id))
    except (TypeError, ValueError):
        metadata_source_artifact_id = None
    if metadata_source_artifact_id != source_artifact.id:
        reasons.append("perceptual evidence report source Artifact metadata is inconsistent")
    return reasons


def _validate_report_payload(
    report: PerceptualEvidenceReport,
    report_version: Version,
    source_version: Version,
) -> list[str]:
    reasons: list[str] = []
    metadata = report_version.metadata
    if report.source_version_id != source_version.id:
        reasons.append("perceptual evidence payload source Version is inconsistent")
    if metadata.get("schema_version") != report.schema_version:
        reasons.append("perceptual evidence schema version metadata is inconsistent")
    if metadata.get("preprocessing_version") != report.preprocessing_version:
        reasons.append("perceptual evidence preprocessing metadata is inconsistent")
    if metadata.get("sample_rate") != report.sample_rate:
        reasons.append("perceptual evidence sample-rate metadata is inconsistent")
    if metadata.get("channel_mode") != report.channel_mode:
        reasons.append("perceptual evidence channel-mode metadata is inconsistent")

    metadata_features = metadata.get("features")
    expected_features = sorted(report.series)
    if (
        not isinstance(metadata_features, list)
        or sorted(str(item) for item in metadata_features) != expected_features
    ):
        reasons.append("perceptual evidence feature metadata is inconsistent")
    return reasons


def compare_persisted_perceptual_spans(
    snapshot: WorkBundleSnapshot,
    *,
    source_version: Version,
    query: PerceptualSpanComparisonQuery,
    load_report: Callable[[Version], bytes],
) -> PerceptualSpanComparisonQueryResult:
    """Resolve, validate, and compare two spans without creating persistent state."""

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

    observation = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version.id,
        subject_locator=SecondsSpanLocator(
            start_seconds=query.subject_start_seconds,
            end_seconds=query.subject_end_seconds,
            source_artifact_version_id=source_version.id,
            authority="user_selected",
        ),
        comparison_locator=SecondsSpanLocator(
            start_seconds=query.comparison_start_seconds,
            end_seconds=query.comparison_end_seconds,
            source_artifact_version_id=source_version.id,
            authority="user_selected",
        ),
    )
    if observation.sufficiency.status != "supported":
        return _result(
            "withheld",
            evidence_report_version_id=report_version.id,
            reasons=list(observation.sufficiency.reasons)
            or [f"relation sufficiency is {observation.sufficiency.status}"],
        )

    finding = compose_grounded_relation_finding(observation)
    if finding is None:
        return _result(
            "failed",
            evidence_report_version_id=report_version.id,
            reasons=["supported relation could not be composed safely"],
        )

    return _result(
        "supported",
        evidence_report_version_id=report_version.id,
        finding=finding,
    )


__all__ = [
    "ComparisonStatus",
    "PerceptualSpanComparisonQuery",
    "PerceptualSpanComparisonQueryResult",
    "compare_persisted_perceptual_spans",
]

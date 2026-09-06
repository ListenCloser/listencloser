"""On-demand query boundary for persisted within-Work rhythm-density context.

The persisted source of truth is the promoted ``rhythm_density`` Insight attached
to the MIDI Version analyzed by ``handle_analyze``. The optional audio input to
that capability supplies pulse evidence but does not own the Insight row. This
module therefore resolves one exact authorized density-owning Version, loads its
Insights through an injected reader, validates the newest density payload, and
derives a contextual product finding without persisting transient relation state.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from domain.models import Artifact, ArtifactKind, Insight, Version
from domain.relation_observations import SecondsSpanLocator
from domain.rhythm_density_context import contextualize_rhythm_density_within_work
from domain.rhythm_density_context_findings import (
    GroundedContextFinding,
    SubjectOrigin,
    compose_grounded_rhythm_density_context_finding,
)
from domain.rhythm_density_relations import RhythmDensityEvidence
from domain.work_bundle_repository import WorkBundleSnapshot

ContextQueryStatus = Literal["supported", "unavailable", "withheld", "failed"]
_ALLOWED_DENSITY_OWNER_KINDS = {
    ArtifactKind.midi_performance,
    ArtifactKind.midi_corrected,
}


class RhythmDensityContextQuery(BaseModel):
    """One explicit seconds-authoritative subject span and its product origin."""

    model_config = ConfigDict(frozen=True)

    subject_start_seconds: float
    subject_end_seconds: float
    subject_origin: SubjectOrigin


class RhythmDensityContextQueryResult(BaseModel):
    """Truthful availability/result state for one persisted context query."""

    model_config = ConfigDict(frozen=True)

    status: ContextQueryStatus
    rhythm_density_insight_id: UUID | None = None
    finding: GroundedContextFinding | None = None
    reasons: list[str] = Field(default_factory=list)


def _result(
    status: ContextQueryStatus,
    *,
    rhythm_density_insight_id: UUID | None = None,
    finding: GroundedContextFinding | None = None,
    reasons: list[str] | None = None,
) -> RhythmDensityContextQueryResult:
    return RhythmDensityContextQueryResult(
        status=status,
        rhythm_density_insight_id=rhythm_density_insight_id,
        finding=finding,
        reasons=list(reasons or []),
    )


def _density_owner_version(
    snapshot: WorkBundleSnapshot,
    version_id: UUID,
) -> tuple[Version | None, Artifact | None, list[str]]:
    matches: list[tuple[Artifact, Version]] = []
    for artifact in snapshot.artifacts:
        for version in snapshot.versions_by_artifact.get(artifact.id, []):
            if version.id == version_id:
                matches.append((artifact, version))

    if not matches:
        return None, None, ["density-owning Version is not part of the authorized Work snapshot"]
    if len(matches) != 1:
        return None, None, ["density-owning Version membership is ambiguous"]

    artifact, version = matches[0]
    if artifact.work_id != snapshot.work.id:
        return None, None, ["density-owning Artifact does not belong to the authorized Work"]
    if version.artifact_id != artifact.id:
        return None, None, ["density-owning Version/Artifact membership is inconsistent"]
    if artifact.kind not in _ALLOWED_DENSITY_OWNER_KINDS:
        return (
            None,
            None,
            ["rhythm density context requires the MIDI Version that owns the persisted Insight"],
        )
    return version, artifact, []


def _utc_timestamp(value: datetime) -> float:
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.timestamp()


def _latest_density_insight(insights: Sequence[Insight]) -> Insight | None:
    candidates = [item for item in insights if item.kind == "rhythm_density"]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (_utc_timestamp(item.created_at), str(item.id)))


def _pulse_provenance(insight: Insight) -> dict | None:
    value = insight.provenance.get("engine")
    return dict(value) if isinstance(value, dict) else None


def _density_evidence(
    insight: Insight,
    density_owner_version: Version,
) -> RhythmDensityEvidence | None:
    if insight.version_id != density_owner_version.id:
        return None
    try:
        return RhythmDensityEvidence(
            evidence_id=insight.id,
            source_version_id=density_owner_version.id,
            windows=insight.evidence.get("windows", []),
            coverage=insight.evidence.get("coverage"),
            pulse_provenance=_pulse_provenance(insight),
        )
    except (ValidationError, TypeError, ValueError):
        return None


def _locator_authority(subject_origin: SubjectOrigin) -> Literal["explicit", "user_selected"]:
    return "user_selected" if subject_origin == "user_selected" else "explicit"


def query_persisted_rhythm_density_context(
    snapshot: WorkBundleSnapshot,
    *,
    density_owner_version_id: UUID,
    query: RhythmDensityContextQuery,
    load_insights: Callable[[Version], Sequence[Insight]],
) -> RhythmDensityContextQueryResult:
    """Resolve, validate, contextualize, and compose one span without DB writes."""

    density_owner_version, _, owner_reasons = _density_owner_version(
        snapshot,
        density_owner_version_id,
    )
    if density_owner_version is None:
        return _result("failed", reasons=owner_reasons)

    try:
        loaded = list(load_insights(density_owner_version))
    except Exception:
        return _result("failed", reasons=["persisted Insights could not be loaded"])
    if not all(isinstance(item, Insight) for item in loaded):
        return _result("failed", reasons=["persisted Insights could not be validated"])

    insight = _latest_density_insight(loaded)
    if insight is None:
        return _result(
            "unavailable",
            reasons=["rhythm density evidence is not available for this Version"],
        )
    if insight.version_id != density_owner_version.id:
        return _result(
            "failed",
            rhythm_density_insight_id=insight.id,
            reasons=["rhythm density Insight Version is inconsistent"],
        )

    evidence = _density_evidence(insight, density_owner_version)
    if evidence is None:
        return _result(
            "failed",
            rhythm_density_insight_id=insight.id,
            reasons=["rhythm density Insight evidence could not be validated"],
        )

    observation = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=SecondsSpanLocator(
            start_seconds=query.subject_start_seconds,
            end_seconds=query.subject_end_seconds,
            source_artifact_version_id=density_owner_version.id,
            authority=_locator_authority(query.subject_origin),
        ),
    )
    if observation.sufficiency.status != "supported":
        return _result(
            "withheld",
            rhythm_density_insight_id=insight.id,
            reasons=list(observation.sufficiency.reasons)
            or [f"context relation sufficiency is {observation.sufficiency.status}"],
        )

    finding = compose_grounded_rhythm_density_context_finding(
        observation,
        subject_origin=query.subject_origin,
    )
    if finding is None:
        return _result(
            "failed",
            rhythm_density_insight_id=insight.id,
            reasons=["supported rhythm density context could not be composed safely"],
        )

    return _result(
        "supported",
        rhythm_density_insight_id=insight.id,
        finding=finding,
    )


__all__ = [
    "ContextQueryStatus",
    "RhythmDensityContextQuery",
    "RhythmDensityContextQueryResult",
    "query_persisted_rhythm_density_context",
]

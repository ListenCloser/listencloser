"""Product-facing literal findings for within-Work rhythm-density context.

This layer translates an already-supported ``RhythmDensityContextObservation``
into concise, auditable product copy. A discontinuous reference population is
kept explicit: the composer never invents a comparison span, inferential
statistics, musical salience, or semantic interpretation.
"""

from __future__ import annotations

import math
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.relation_observations import RelationSufficiency, SecondsSpanLocator
from domain.rhythm_density_context import (
    RhythmDensityContextMeasurement,
    RhythmDensityContextObservation,
    RhythmDensityReferencePopulation,
)
from domain.rhythm_density_relations import RhythmDensityEvidenceRef

ContextFindingAction = Literal["focus", "evidence"]
SubjectOrigin = Literal[
    "user_selected",
    "legacy_density_peak",
    "legacy_density_valley",
    "other_grounded_candidate",
]

_COMPOSER_VERSION = "1.0"
_NUMERIC_ATOL = 1e-12
_NUMERIC_RTOL = 1e-9
_EXPECTED_COMPARISON_LOCATOR_SEMANTICS = "none_discontinuous_reference_population"
_EXPECTED_PERCENTILE_CONVENTION = "empirical_midrank_reference_windows_v1"
_EXPECTED_RANK_TARGET = "subject_median_vs_reference_window_values"


class GroundedContextFindingMeasurement(BaseModel):
    """One literal density-context measurement tied to its exact evidence ref."""

    model_config = ConfigDict(frozen=True)

    support_ref: RhythmDensityEvidenceRef
    feature: Literal["rhythm_density"] = "rhythm_density"
    direction: Literal["higher", "lower", "unchanged"]
    summary: str
    unit: Literal["events_per_beat"] = "events_per_beat"
    normalization: Literal["events_per_beat"] = "events_per_beat"
    coordinate_unit: Literal["beats"] = "beats"
    window_size: float = Field(gt=0)
    step_size: float = Field(gt=0)
    subject_value: float
    reference_median: float
    reference_q1: float
    reference_q3: float
    reference_iqr: float = Field(ge=0)
    delta_from_reference_median: float
    empirical_midrank_percentile: float = Field(ge=0, le=100)
    subject_window_count: int = Field(ge=1)
    reference_window_count: int = Field(ge=1)


class GroundedContextFinding(BaseModel):
    """Context relation translated into literal product-facing evidence."""

    model_config = ConfigDict(frozen=True)

    id: str
    source_relation_id: UUID
    kind: Literal["rhythm_density_work_context"] = "rhythm_density_work_context"
    relation_kind: Literal["compare"] = "compare"
    trust_class: Literal["deterministic_derived"] = "deterministic_derived"
    maturity: Literal["production"] = "production"
    subject_locator: SecondsSpanLocator
    reference_population: RhythmDensityReferencePopulation
    support_refs: list[RhythmDensityEvidenceRef]
    measurements: list[GroundedContextFindingMeasurement]
    sufficiency: RelationSufficiency
    subject_origin: SubjectOrigin
    selection_conditioned_on_rhythm_density: bool | None
    headline: str
    evidence_summary: str
    available_actions: list[ContextFindingAction]
    provenance: dict[str, Any] = Field(default_factory=dict)


def _valid_locator(locator: SecondsSpanLocator) -> bool:
    return (
        math.isfinite(locator.start_seconds)
        and math.isfinite(locator.end_seconds)
        and locator.start_seconds >= 0
        and locator.end_seconds > locator.start_seconds
    )


def _selection_conditioning(subject_origin: SubjectOrigin) -> bool | None:
    if subject_origin == "user_selected":
        return False
    if subject_origin in {"legacy_density_peak", "legacy_density_valley"}:
        return True
    return None


def _finite(values: tuple[float, ...]) -> bool:
    return all(math.isfinite(value) for value in values)


def _direction(delta: float) -> Literal["higher", "lower", "unchanged"]:
    if math.isclose(delta, 0.0, abs_tol=_NUMERIC_ATOL, rel_tol=_NUMERIC_RTOL):
        return "unchanged"
    return "higher" if delta > 0 else "lower"


def _valid_reference_population(
    population: RhythmDensityReferencePopulation,
    measurement: RhythmDensityContextMeasurement,
) -> bool:
    if population.kind != "work_excluding_subject":
        return False
    if population.eligible_window_count != measurement.reference_window_count:
        return False
    if population.eligible_window_count < 1:
        return False
    if population.excluded_intersecting_window_count < 1:
        return False
    if not _finite(
        (
            population.source_coverage_start_seconds,
            population.source_coverage_end_seconds,
            population.eligible_coverage_seconds,
        )
    ):
        return False
    if population.source_coverage_start_seconds < 0:
        return False
    if population.source_coverage_end_seconds <= population.source_coverage_start_seconds:
        return False
    if population.eligible_coverage_seconds < 0:
        return False

    previous_end: float | None = None
    interval_coverage = 0.0
    for start, end in population.eligible_intervals_seconds:
        if not _finite((start, end)) or start < 0 or end <= start:
            return False
        if previous_end is not None and start <= previous_end + _NUMERIC_ATOL:
            return False
        interval_coverage += end - start
        previous_end = end
    return math.isclose(
        interval_coverage,
        population.eligible_coverage_seconds,
        abs_tol=_NUMERIC_ATOL,
        rel_tol=_NUMERIC_RTOL,
    )


def _valid_measurement(measurement: RhythmDensityContextMeasurement) -> bool:
    numeric_values = (
        measurement.window_size,
        measurement.step_size,
        measurement.subject_value,
        measurement.reference_median,
        measurement.reference_q1,
        measurement.reference_q3,
        measurement.reference_iqr,
        measurement.delta_from_reference_median,
        measurement.empirical_midrank_percentile,
    )
    if not _finite(numeric_values):
        return False
    if measurement.unit != "events_per_beat":
        return False
    if measurement.normalization != "events_per_beat":
        return False
    if measurement.coordinate_unit != "beats":
        return False
    if measurement.reference_q1 > measurement.reference_median + _NUMERIC_ATOL:
        return False
    if measurement.reference_median > measurement.reference_q3 + _NUMERIC_ATOL:
        return False
    if not math.isclose(
        measurement.reference_iqr,
        measurement.reference_q3 - measurement.reference_q1,
        abs_tol=_NUMERIC_ATOL,
        rel_tol=_NUMERIC_RTOL,
    ):
        return False

    expected_delta = measurement.subject_value - measurement.reference_median
    if not math.isclose(
        measurement.delta_from_reference_median,
        expected_delta,
        abs_tol=_NUMERIC_ATOL,
        rel_tol=_NUMERIC_RTOL,
    ):
        return False
    return measurement.direction == _direction(expected_delta)


def _valid_relation_provenance(observation: RhythmDensityContextObservation) -> bool:
    provenance = observation.provenance
    return (
        provenance.get("comparison_locator_semantics") == _EXPECTED_COMPARISON_LOCATOR_SEMANTICS
        and provenance.get("percentile_convention") == _EXPECTED_PERCENTILE_CONVENTION
        and provenance.get("rank_target") == _EXPECTED_RANK_TARGET
        and provenance.get("reference_window_independence_assumed") is False
        and provenance.get("inferential_statistics_emitted") is False
        and provenance.get("semantic_interpretation_emitted") is False
    )


def _measurement_summary(measurement: RhythmDensityContextMeasurement) -> str:
    if measurement.direction == "unchanged":
        return (
            "Median event density here matches the median elsewhere in this Work "
            f"({measurement.subject_value:.3g} events/beat)."
        )
    return (
        f"Median event density here is {measurement.direction} than the median elsewhere "
        f"in this Work ({measurement.subject_value:.3g} vs "
        f"{measurement.reference_median:.3g} events/beat)."
    )


def _evidence_summary(measurement: RhythmDensityContextMeasurement) -> str:
    return (
        f"Middle half elsewhere in this Work: {measurement.reference_q1:.3g}–"
        f"{measurement.reference_q3:.3g} events/beat."
    )


def compose_grounded_rhythm_density_context_finding(
    observation: RhythmDensityContextObservation,
    *,
    subject_origin: SubjectOrigin,
) -> GroundedContextFinding | None:
    """Compose literal product copy from one supported density-context observation."""

    if observation.sufficiency.status != "supported":
        return None
    if observation.comparison_locator is not None:
        return None
    if not _valid_locator(observation.subject_locator):
        return None
    if observation.reference_population is None:
        return None
    if not _valid_relation_provenance(observation):
        return None
    if len(observation.support_refs) != 1 or len(observation.measurements) != 1:
        return None

    support_ref = observation.support_refs[0]
    measurement = observation.measurements[0]
    if support_ref.namespace != "rhythm_density_insight":
        return None
    if not support_ref.id.endswith(":rhythm_density"):
        return None
    if not _valid_measurement(measurement):
        return None
    if not _valid_reference_population(observation.reference_population, measurement):
        return None

    selection_conditioned = _selection_conditioning(subject_origin)
    summary = _measurement_summary(measurement)
    composed_measurement = GroundedContextFindingMeasurement(
        support_ref=support_ref,
        direction=measurement.direction,
        summary=summary,
        window_size=measurement.window_size,
        step_size=measurement.step_size,
        subject_value=measurement.subject_value,
        reference_median=measurement.reference_median,
        reference_q1=measurement.reference_q1,
        reference_q3=measurement.reference_q3,
        reference_iqr=measurement.reference_iqr,
        delta_from_reference_median=measurement.delta_from_reference_median,
        empirical_midrank_percentile=measurement.empirical_midrank_percentile,
        subject_window_count=measurement.subject_window_count,
        reference_window_count=measurement.reference_window_count,
    )

    provenance = dict(observation.provenance)
    provenance.update(
        {
            "composer": "rhythm_density_context_finding",
            "composer_version": _COMPOSER_VERSION,
            "subject_origin": subject_origin,
            "selection_conditioned_on_rhythm_density": selection_conditioned,
            "salience_independence_claimed": False,
        }
    )

    return GroundedContextFinding(
        id=f"context-finding-{observation.id}",
        source_relation_id=observation.id,
        kind=observation.kind,
        relation_kind=observation.relation_kind,
        trust_class=observation.trust_class,
        maturity=observation.maturity,
        subject_locator=observation.subject_locator,
        reference_population=observation.reference_population,
        support_refs=[support_ref],
        measurements=[composed_measurement],
        sufficiency=observation.sufficiency,
        subject_origin=subject_origin,
        selection_conditioned_on_rhythm_density=selection_conditioned,
        headline=summary,
        evidence_summary=_evidence_summary(measurement),
        available_actions=["focus", "evidence"],
        provenance=provenance,
    )


__all__ = [
    "ContextFindingAction",
    "GroundedContextFinding",
    "GroundedContextFindingMeasurement",
    "SubjectOrigin",
    "compose_grounded_rhythm_density_context_finding",
]

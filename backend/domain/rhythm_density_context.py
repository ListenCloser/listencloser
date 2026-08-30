"""Descriptive within-Work context over promoted rhythm-density evidence.

This module extends the landed rhythm-density relation contract with one bounded
reference population: compatible complete windows elsewhere in the same Work.
It intentionally remains evidence-family-specific and descriptive. Overlapping
sliding windows are not treated as independent samples, and no musical
importance/significance semantics are emitted here.
"""

from __future__ import annotations

import math
from typing import Any, Literal
from uuid import UUID, uuid4

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from domain.relation_observations import (
    BoundarySensitivityHook,
    RelationSufficiency,
    SecondsSpanLocator,
)
from domain.rhythm_density_relations import (
    RhythmDensityEvidence,
    RhythmDensityEvidenceRef,
    _NUMERIC_ATOL,
    _NUMERIC_RTOL,
    _coverage_error_for_span,
    _direction,
    _validate_locator,
    _validated_persistence_coverage,
    _validated_windows,
    _values_for_span,
)

_CONTEXT_ENGINE_VERSION = "1.0"
_COMPLETE_SERIES_POLICY = "complete_series_v1"
_MIN_REFERENCE_WINDOWS = 4
_QUARTILE_METHOD = "linear"
_PERCENTILE_CONVENTION = "empirical_midrank_reference_windows_v1"
_EXCLUSION_POLICY = "exclude_intersecting_subject_windows_v1"


class RhythmDensityReferencePopulation(BaseModel):
    """Explicit discontinuous within-Work reference population."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["work_excluding_subject"] = "work_excluding_subject"
    exclusion_policy: Literal["exclude_intersecting_subject_windows_v1"] = _EXCLUSION_POLICY
    eligible_window_count: int = Field(ge=0)
    excluded_intersecting_window_count: int = Field(ge=0)
    source_coverage_start_seconds: float
    source_coverage_end_seconds: float
    eligible_intervals_seconds: list[tuple[float, float]] = Field(default_factory=list)
    eligible_coverage_seconds: float = Field(ge=0)


class RhythmDensityContextMeasurement(BaseModel):
    """Literal descriptive location of a subject within compatible Work evidence."""

    model_config = ConfigDict(frozen=True)

    feature: Literal["rhythm_density"] = "rhythm_density"
    aggregate: Literal["median"] = "median"
    unit: Literal["events_per_beat"] = "events_per_beat"
    normalization: Literal["events_per_beat"] = "events_per_beat"
    coordinate_unit: Literal["beats"] = "beats"
    window_size: float = Field(gt=0)
    step_size: float = Field(gt=0)
    subject_value: float
    reference_median: float
    reference_q1: float
    reference_q3: float
    delta_from_reference_median: float
    direction: Literal["higher", "lower", "unchanged"]
    empirical_midrank_percentile: float = Field(ge=0, le=100)
    quartile_method: Literal["linear"] = _QUARTILE_METHOD
    percentile_convention: Literal["empirical_midrank_reference_windows_v1"] = (
        _PERCENTILE_CONVENTION
    )
    subject_window_count: int = Field(ge=1)
    reference_window_count: int = Field(ge=_MIN_REFERENCE_WINDOWS)


class RhythmDensityContextObservation(BaseModel):
    """Relation-style observation against a typed non-contiguous reference set."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    kind: Literal["rhythm_density_work_context"] = "rhythm_density_work_context"
    relation_kind: Literal["compare"] = "compare"
    trust_class: Literal["deterministic_derived"] = "deterministic_derived"
    maturity: Literal["production"] = "production"
    subject_locator: SecondsSpanLocator
    reference_population: RhythmDensityReferencePopulation | None = None
    support_refs: list[RhythmDensityEvidenceRef] = Field(default_factory=list)
    measurements: list[RhythmDensityContextMeasurement] = Field(default_factory=list)
    sufficiency: RelationSufficiency
    provenance: dict[str, Any] = Field(default_factory=dict)
    sensitivity: BoundarySensitivityHook = Field(default_factory=BoundarySensitivityHook)


def _provenance(
    evidence: RhythmDensityEvidence,
    contract: dict[str, float | str] | None,
) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "engine": "rhythm_density_work_context",
        "engine_version": _CONTEXT_ENGINE_VERSION,
        "aggregate": "median",
        "reference_population": "work_excluding_subject",
        "reference_exclusion_policy": _EXCLUSION_POLICY,
        "minimum_reference_window_count": _MIN_REFERENCE_WINDOWS,
        "quartile_method": _QUARTILE_METHOD,
        "percentile_convention": _PERCENTILE_CONVENTION,
        "reference_window_independence_assumed": False,
        "source_version_id": str(evidence.source_version_id),
        "evidence_id": str(evidence.evidence_id),
        "semantic_interpretation_emitted": False,
    }
    if contract is not None:
        provenance["evidence_contract"] = dict(contract)
    if evidence.coverage is not None:
        provenance["persistence_coverage"] = dict(evidence.coverage)
    if evidence.pulse_provenance is not None:
        provenance["pulse_provenance"] = evidence.pulse_provenance
    return provenance


def _withheld(
    evidence: RhythmDensityEvidence,
    subject_locator: SecondsSpanLocator,
    reasons: list[str],
    contract: dict[str, float | str] | None = None,
    reference_population: RhythmDensityReferencePopulation | None = None,
) -> RhythmDensityContextObservation:
    return RhythmDensityContextObservation(
        subject_locator=subject_locator,
        reference_population=reference_population,
        support_refs=[],
        measurements=[],
        sufficiency=RelationSufficiency(status="withhold", reasons=reasons),
        provenance=_provenance(evidence, contract),
    )


def _work_reference_windows(
    windows: list[dict[str, float]],
    subject_locator: SecondsSpanLocator,
) -> tuple[list[dict[str, float]], int]:
    eligible: list[dict[str, float]] = []
    excluded = 0
    for window in windows:
        outside_subject = (
            window["end"] <= subject_locator.start_seconds + _NUMERIC_ATOL
            or window["start"] >= subject_locator.end_seconds - _NUMERIC_ATOL
        )
        if outside_subject:
            eligible.append(window)
        else:
            excluded += 1
    return eligible, excluded


def _merged_intervals(windows: list[dict[str, float]]) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    for window in windows:
        start = window["start"]
        end = window["end"]
        if not intervals or start > intervals[-1][1] + _NUMERIC_ATOL:
            intervals.append((start, end))
            continue
        previous_start, previous_end = intervals[-1]
        intervals[-1] = (previous_start, max(previous_end, end))
    return intervals


def _reference_population(
    windows: list[dict[str, float]],
    reference_windows: list[dict[str, float]],
    excluded_count: int,
) -> RhythmDensityReferencePopulation:
    intervals = _merged_intervals(reference_windows)
    return RhythmDensityReferencePopulation(
        eligible_window_count=len(reference_windows),
        excluded_intersecting_window_count=excluded_count,
        source_coverage_start_seconds=windows[0]["start"],
        source_coverage_end_seconds=max(window["end"] for window in windows),
        eligible_intervals_seconds=intervals,
        eligible_coverage_seconds=sum(end - start for start, end in intervals),
    )


def _empirical_midrank_percentile(subject_value: float, reference_values: np.ndarray) -> float:
    equal = np.isclose(
        reference_values,
        subject_value,
        atol=_NUMERIC_ATOL,
        rtol=_NUMERIC_RTOL,
    )
    lower = np.logical_and(reference_values < subject_value, np.logical_not(equal))
    return 100.0 * (float(np.count_nonzero(lower)) + 0.5 * float(np.count_nonzero(equal))) / len(
        reference_values
    )


def contextualize_rhythm_density_within_work(
    evidence: RhythmDensityEvidence,
    *,
    subject_locator: SecondsSpanLocator,
) -> RhythmDensityContextObservation:
    """Compare one explicit subject span with compatible windows elsewhere in its Work.

    V1 requires the complete persisted beat-relative density series. Every
    evidence window that temporally intersects the subject is excluded from the
    reference set. Outputs are descriptive distribution statistics only; they
    are not p-values, significance tests, or claims about musical importance.
    """

    reasons = _validate_locator(subject_locator, evidence, "subject")
    windows, contract, contract_reasons = _validated_windows(evidence)
    reasons.extend(contract_reasons)

    if not contract_reasons:
        if contract is None:
            reasons.append("rhythm density evidence contract is unavailable")
        elif evidence.coverage is None:
            reasons.append("within-Work context requires complete_series_v1 persistence coverage")
        else:
            reasons.extend(_validated_persistence_coverage(evidence, windows, contract))
            if evidence.coverage.get("policy_version") != _COMPLETE_SERIES_POLICY:
                reasons.append("within-Work context requires complete_series_v1 persistence coverage")

    if reasons:
        return _withheld(evidence, subject_locator, reasons, contract)

    assert contract is not None
    coverage_error = _coverage_error_for_span(windows, contract, subject_locator, "subject")
    if coverage_error:
        return _withheld(evidence, subject_locator, [coverage_error], contract)

    subject_values, subject_error = _values_for_span(windows, subject_locator, "subject")
    if subject_error or subject_values is None:
        return _withheld(
            evidence,
            subject_locator,
            [subject_error or "subject rhythm density evidence is unavailable"],
            contract,
        )

    reference_windows, excluded_count = _work_reference_windows(windows, subject_locator)
    population = _reference_population(windows, reference_windows, excluded_count)
    if len(reference_windows) < _MIN_REFERENCE_WINDOWS:
        return _withheld(
            evidence,
            subject_locator,
            [
                "within-Work context requires at least "
                f"{_MIN_REFERENCE_WINDOWS} compatible reference windows outside the subject"
            ],
            contract,
            population,
        )

    reference_values = np.asarray([window["density"] for window in reference_windows], dtype=float)
    subject_value = float(np.median(subject_values))
    reference_median = float(np.median(reference_values))
    q1, q3 = np.percentile(reference_values, [25.0, 75.0], method=_QUARTILE_METHOD)
    delta = subject_value - reference_median
    percentile = _empirical_midrank_percentile(subject_value, reference_values)

    numeric_values = (subject_value, reference_median, float(q1), float(q3), delta, percentile)
    if not all(math.isfinite(value) for value in numeric_values):
        return _withheld(
            evidence,
            subject_locator,
            ["within-Work rhythm density statistics are non-finite"],
            contract,
            population,
        )

    measurement = RhythmDensityContextMeasurement(
        window_size=float(contract["window_size"]),
        step_size=float(contract["step_size"]),
        subject_value=subject_value,
        reference_median=reference_median,
        reference_q1=float(q1),
        reference_q3=float(q3),
        delta_from_reference_median=delta,
        direction=_direction(delta),
        empirical_midrank_percentile=percentile,
        subject_window_count=len(subject_values),
        reference_window_count=len(reference_values),
    )
    return RhythmDensityContextObservation(
        subject_locator=subject_locator,
        reference_population=population,
        support_refs=[RhythmDensityEvidenceRef(id=f"{evidence.evidence_id}:rhythm_density")],
        measurements=[measurement],
        sufficiency=RelationSufficiency(status="supported"),
        provenance=_provenance(evidence, contract),
    )


__all__ = [
    "RhythmDensityContextMeasurement",
    "RhythmDensityContextObservation",
    "RhythmDensityReferencePopulation",
    "contextualize_rhythm_density_within_work",
]

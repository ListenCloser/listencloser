"""Descriptive within-Work contextual relations over rhythm-density evidence.

The first contextual M2 relation intentionally reuses the promoted rhythm-density
A/B contract as its evidence validator. It adds a typed reference population and
robust descriptive statistics, without inferential or semantic interpretation.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from domain.relation_observations import (
    RelationObservation,
    RelationSufficiency,
    SecondsSpanLocator,
)
from domain.rhythm_density_relations import (
    RhythmDensityEvidence,
    RhythmDensityEvidenceRef,
    compare_rhythm_density_spans,
)

_CONTEXT_ENGINE_VERSION = "1.0"
_COMPLETE_SERIES_POLICY = "complete_series_v1"
_MIN_REFERENCE_WINDOWS = 5
_NUMERIC_ATOL = 1e-12
_NUMERIC_RTOL = 1e-9
_RELATIVE_DENOMINATOR_EPSILON = 1e-9

RhythmDensityReferenceKind = Literal["work_excluding_subject", "local_context"]


class RhythmDensityReferencePopulation(BaseModel):
    """Exact within-Work reference population used by a contextual relation."""

    model_config = ConfigDict(frozen=True)

    kind: RhythmDensityReferenceKind
    context_radius_seconds: float | None = None
    envelope_start_seconds: float
    envelope_end_seconds: float
    eligible_window_count: int = Field(ge=0)
    covered_seconds: float = Field(ge=0)
    before_subject_window_count: int = Field(ge=0)
    after_subject_window_count: int = Field(ge=0)
    subject_intersection_policy: Literal["exclude_any_intersection"] = (
        "exclude_any_intersection"
    )
    complete_series_policy: Literal["complete_series_v1"] = _COMPLETE_SERIES_POLICY
    independent_observations_assumed: Literal[False] = False


class RhythmDensityContextMeasurement(BaseModel):
    """Literal descriptive statistics for one subject against a reference set."""

    model_config = ConfigDict(frozen=True)

    feature: Literal["rhythm_density"] = "rhythm_density"
    aggregate: Literal["median"] = "median"
    unit: Literal["events_per_beat"] = "events_per_beat"
    normalization: Literal["events_per_beat"] = "events_per_beat"
    coordinate_unit: Literal["beats"] = "beats"
    window_size: float = Field(gt=0)
    step_size: float = Field(gt=0)
    subject_value: float
    comparison_value: float
    delta: float
    relative_delta: float | None = None
    direction: Literal["higher", "lower", "unchanged"]
    reference_q1: float
    reference_q3: float
    reference_iqr: float = Field(ge=0)
    subject_midrank_percentile: float = Field(ge=0, le=100)
    subject_window_count: int = Field(ge=1)
    reference_window_count: int = Field(ge=1)
    reference_covered_seconds: float = Field(ge=0)


class RhythmDensityContextObservation(RelationObservation):
    """RelationObservation specialization for within-Work contextual density."""

    kind: Literal["rhythm_density_context_comparison"] = (
        "rhythm_density_context_comparison"
    )
    comparison_locator: SecondsSpanLocator | None = None
    support_refs: list[RhythmDensityEvidenceRef] = Field(default_factory=list)
    measurements: list[RhythmDensityContextMeasurement] = Field(default_factory=list)
    reference_population: RhythmDensityReferencePopulation | None = None


def _context_provenance(
    evidence: RhythmDensityEvidence,
    *,
    reference_kind: RhythmDensityReferenceKind,
    context_radius_seconds: float | None,
    evidence_contract: dict | None,
) -> dict:
    provenance = {
        "engine": "rhythm_density_context_compare",
        "engine_version": _CONTEXT_ENGINE_VERSION,
        "source_version_id": str(evidence.source_version_id),
        "evidence_id": str(evidence.evidence_id),
        "subject_aggregate": "median",
        "reference_summary": "median_iqr_empirical_midrank",
        "rank_target": "subject_median_vs_reference_window_values",
        "midrank_definition": (
            "100 * (count_less + 0.5 * count_equal) / reference_count"
        ),
        "minimum_reference_window_count": _MIN_REFERENCE_WINDOWS,
        "reference_kind": reference_kind,
        "subject_intersection_policy": "exclude_any_intersection",
        "reference_windows_are_correlated": True,
        "independent_observations_assumed": False,
        "inferential_statistics_emitted": False,
        "semantic_interpretation_emitted": False,
    }
    if context_radius_seconds is not None and math.isfinite(context_radius_seconds):
        provenance["context_radius_seconds"] = context_radius_seconds
    if evidence_contract is not None:
        provenance["evidence_contract"] = dict(evidence_contract)
    if evidence.coverage is not None:
        provenance["persistence_coverage"] = dict(evidence.coverage)
    if evidence.pulse_provenance is not None:
        provenance["pulse_provenance"] = evidence.pulse_provenance
    return provenance


def _withheld(
    evidence: RhythmDensityEvidence,
    subject_locator: SecondsSpanLocator,
    reasons: list[str],
    *,
    reference_kind: RhythmDensityReferenceKind,
    context_radius_seconds: float | None,
    evidence_contract: dict | None = None,
    comparison_locator: SecondsSpanLocator | None = None,
    reference_population: RhythmDensityReferencePopulation | None = None,
) -> RhythmDensityContextObservation:
    return RhythmDensityContextObservation(
        subject_locator=subject_locator,
        comparison_locator=comparison_locator,
        support_refs=[],
        measurements=[],
        reference_population=reference_population,
        sufficiency=RelationSufficiency(status="withhold", reasons=reasons),
        provenance=_context_provenance(
            evidence,
            reference_kind=reference_kind,
            context_radius_seconds=context_radius_seconds,
            evidence_contract=evidence_contract,
        ),
    )


def _normalized_windows(evidence: RhythmDensityEvidence) -> list[dict[str, float]]:
    return [
        {
            "start": float(window["start"]),
            "end": float(window["end"]),
            "density": float(window["density"]),
        }
        for window in evidence.windows
    ]


def _intersects_subject(
    window: dict[str, float],
    subject_locator: SecondsSpanLocator,
) -> bool:
    return (
        window["start"] < subject_locator.end_seconds - _NUMERIC_ATOL
        and window["end"] > subject_locator.start_seconds + _NUMERIC_ATOL
    )


def _covered_seconds(windows: list[dict[str, float]]) -> float:
    if not windows:
        return 0.0
    intervals = sorted((window["start"], window["end"]) for window in windows)
    current_start, current_end = intervals[0]
    covered = 0.0
    for start, end in intervals[1:]:
        if start <= current_end + _NUMERIC_ATOL:
            current_end = max(current_end, end)
        else:
            covered += current_end - current_start
            current_start, current_end = start, end
    return covered + current_end - current_start


def _reference_locator(
    evidence: RhythmDensityEvidence,
    subject_locator: SecondsSpanLocator,
    *,
    reference_kind: RhythmDensityReferenceKind,
    context_radius_seconds: float | None,
) -> SecondsSpanLocator:
    assert evidence.coverage is not None
    coverage_start = float(evidence.coverage["start_seconds"])
    coverage_end = float(evidence.coverage["end_seconds"])

    if reference_kind == "work_excluding_subject":
        start_seconds = coverage_start
        end_seconds = coverage_end
    else:
        assert context_radius_seconds is not None
        start_seconds = max(
            coverage_start,
            subject_locator.start_seconds - context_radius_seconds,
        )
        end_seconds = min(
            coverage_end,
            subject_locator.end_seconds + context_radius_seconds,
        )

    return SecondsSpanLocator(
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        source_artifact_version_id=evidence.source_version_id,
        authority="trusted",
    )


def _reference_windows(
    windows: list[dict[str, float]],
    subject_locator: SecondsSpanLocator,
    comparison_locator: SecondsSpanLocator,
) -> tuple[list[dict[str, float]], int, int]:
    selected: list[dict[str, float]] = []
    before_count = 0
    after_count = 0
    for window in windows:
        if window["start"] < comparison_locator.start_seconds - _NUMERIC_ATOL:
            continue
        if window["end"] > comparison_locator.end_seconds + _NUMERIC_ATOL:
            continue
        if _intersects_subject(window, subject_locator):
            continue
        selected.append(window)
        if window["end"] <= subject_locator.start_seconds + _NUMERIC_ATOL:
            before_count += 1
        elif window["start"] >= subject_locator.end_seconds - _NUMERIC_ATOL:
            after_count += 1
    return selected, before_count, after_count


def _midrank_percentile(reference_values: np.ndarray, subject_value: float) -> float:
    close = np.isclose(
        reference_values,
        subject_value,
        atol=_NUMERIC_ATOL,
        rtol=_NUMERIC_RTOL,
    )
    less = np.logical_and(reference_values < subject_value, np.logical_not(close))
    return float(
        100.0
        * (float(np.count_nonzero(less)) + 0.5 * float(np.count_nonzero(close)))
        / float(len(reference_values))
    )


def _relative_delta(delta: float, comparison_value: float) -> float | None:
    if abs(comparison_value) <= _RELATIVE_DENOMINATOR_EPSILON:
        return None
    return delta / abs(comparison_value)


def _direction(delta: float) -> Literal["higher", "lower", "unchanged"]:
    if math.isclose(delta, 0.0, abs_tol=_NUMERIC_ATOL, rel_tol=_NUMERIC_RTOL):
        return "unchanged"
    return "higher" if delta > 0 else "lower"


def compare_rhythm_density_to_context(
    evidence: RhythmDensityEvidence,
    *,
    subject_locator: SecondsSpanLocator,
    reference_kind: RhythmDensityReferenceKind = "work_excluding_subject",
    context_radius_seconds: float | None = None,
) -> RhythmDensityContextObservation:
    """Compare one selected span to a complete descriptive within-Work reference set."""

    subject_relation = compare_rhythm_density_spans(
        evidence,
        subject_locator=subject_locator,
        comparison_locator=subject_locator,
    )
    evidence_contract = subject_relation.provenance.get("evidence_contract")
    reasons: list[str] = []
    if subject_relation.sufficiency.status != "supported":
        reasons.extend(
            f"subject evidence: {reason}"
            for reason in subject_relation.sufficiency.reasons
        )

    coverage = evidence.coverage
    if coverage is None:
        reasons.append(
            "complete persistence coverage metadata is required for contextual comparison"
        )
    elif coverage.get("policy_version") != _COMPLETE_SERIES_POLICY:
        reasons.append("contextual comparison requires complete_series_v1 coverage")

    if reference_kind == "work_excluding_subject":
        if context_radius_seconds is not None:
            reasons.append("context radius is only valid for local_context")
    elif reference_kind == "local_context":
        if (
            context_radius_seconds is None
            or not math.isfinite(context_radius_seconds)
            or context_radius_seconds <= 0
        ):
            reasons.append("local_context requires a positive finite context radius")
    else:
        reasons.append(f"unsupported rhythm density reference population: {reference_kind}")

    if reasons:
        return _withheld(
            evidence,
            subject_locator,
            reasons,
            reference_kind=reference_kind,
            context_radius_seconds=context_radius_seconds,
            evidence_contract=evidence_contract,
        )

    comparison_locator = _reference_locator(
        evidence,
        subject_locator,
        reference_kind=reference_kind,
        context_radius_seconds=context_radius_seconds,
    )
    if comparison_locator.end_seconds <= comparison_locator.start_seconds:
        return _withheld(
            evidence,
            subject_locator,
            ["reference population has non-positive temporal coverage"],
            reference_kind=reference_kind,
            context_radius_seconds=context_radius_seconds,
            evidence_contract=evidence_contract,
            comparison_locator=comparison_locator,
        )

    windows = _normalized_windows(evidence)
    reference_windows, before_count, after_count = _reference_windows(
        windows,
        subject_locator,
        comparison_locator,
    )
    population = RhythmDensityReferencePopulation(
        kind=reference_kind,
        context_radius_seconds=context_radius_seconds,
        envelope_start_seconds=comparison_locator.start_seconds,
        envelope_end_seconds=comparison_locator.end_seconds,
        eligible_window_count=len(reference_windows),
        covered_seconds=_covered_seconds(reference_windows),
        before_subject_window_count=before_count,
        after_subject_window_count=after_count,
    )

    reasons = []
    if len(reference_windows) < _MIN_REFERENCE_WINDOWS:
        reasons.append(
            f"contextual comparison requires at least {_MIN_REFERENCE_WINDOWS} "
            "eligible reference windows"
        )
    if reference_kind == "local_context" and (before_count == 0 or after_count == 0):
        reasons.append("local_context requires eligible evidence before and after the subject")
    if reasons:
        return _withheld(
            evidence,
            subject_locator,
            reasons,
            reference_kind=reference_kind,
            context_radius_seconds=context_radius_seconds,
            evidence_contract=evidence_contract,
            comparison_locator=comparison_locator,
            reference_population=population,
        )

    assert len(subject_relation.measurements) == 1
    subject_measurement = subject_relation.measurements[0]
    subject_value = float(subject_measurement.subject_value)
    reference_values = np.asarray(
        [window["density"] for window in reference_windows],
        dtype=float,
    )
    reference_median = float(np.median(reference_values))
    q1, q3 = np.percentile(reference_values, [25.0, 75.0], method="linear")
    reference_q1 = float(q1)
    reference_q3 = float(q3)
    delta = subject_value - reference_median

    measurement = RhythmDensityContextMeasurement(
        window_size=subject_measurement.window_size,
        step_size=subject_measurement.step_size,
        subject_value=subject_value,
        comparison_value=reference_median,
        delta=delta,
        relative_delta=_relative_delta(delta, reference_median),
        direction=_direction(delta),
        reference_q1=reference_q1,
        reference_q3=reference_q3,
        reference_iqr=reference_q3 - reference_q1,
        subject_midrank_percentile=_midrank_percentile(reference_values, subject_value),
        subject_window_count=subject_measurement.subject_window_count,
        reference_window_count=len(reference_windows),
        reference_covered_seconds=population.covered_seconds,
    )
    return RhythmDensityContextObservation(
        subject_locator=subject_locator,
        comparison_locator=comparison_locator,
        support_refs=list(subject_relation.support_refs),
        measurements=[measurement],
        reference_population=population,
        sufficiency=RelationSufficiency(status="supported"),
        provenance=_context_provenance(
            evidence,
            reference_kind=reference_kind,
            context_radius_seconds=context_radius_seconds,
            evidence_contract=evidence_contract,
        ),
    )


__all__ = [
    "RhythmDensityContextMeasurement",
    "RhythmDensityContextObservation",
    "RhythmDensityReferenceKind",
    "RhythmDensityReferencePopulation",
    "compare_rhythm_density_to_context",
]

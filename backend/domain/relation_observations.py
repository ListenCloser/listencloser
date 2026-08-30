"""Deterministic relation observations over promoted measured evidence.

The first M2 relation is deliberately narrow: compare two explicit seconds spans
inside one canonical :class:`PerceptualEvidenceReport`. It emits literal numeric
relations only and withholds on incompatible lineage, preprocessing, coverage, or
values instead of falling back to weaker evidence or semantic interpretation.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import median
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from domain.perceptual_report import (
    FeatureName,
    PerceptualEvidenceReport,
    PerceptualSeriesEvidence,
)

_RELATION_ENGINE_VERSION = "1.0"
_RELATIVE_DENOMINATOR_EPSILON = 1e-9
_NUMERIC_ATOL = 1e-12
_NUMERIC_RTOL = 1e-9
_SUPPORTED_FEATURES: tuple[FeatureName, ...] = (
    "rms",
    "spectral_centroid",
    "relative_band_energy",
    "onset_strength",
)

Numeric = float | list[float]
FrameValues = list[float] | list[list[float]]


class SecondsSpanLocator(BaseModel):
    """Seconds-authoritative span whose validity is decided by sufficiency logic."""

    model_config = ConfigDict(frozen=True)

    start_seconds: float
    end_seconds: float
    source_artifact_version_id: UUID
    authority: Literal["explicit", "user_selected", "trusted"] = "explicit"


class EvidenceRef(BaseModel):
    """#371-compatible namespaced reference to one series inside an analysis report."""

    model_config = ConfigDict(frozen=True)

    type: Literal["external"] = "external"
    namespace: Literal["perceptual_series"] = "perceptual_series"
    id: str


class RelationMeasurement(BaseModel):
    """One literal evidence-specific A/B aggregate and numeric relation."""

    model_config = ConfigDict(frozen=True)

    feature: FeatureName
    aggregate: Literal["median"] = "median"
    unit: str | None
    normalization: str
    components: list[str] = Field(default_factory=list)
    subject_value: float | list[float]
    comparison_value: float | list[float]
    delta: float | list[float]
    relative_delta: float | list[float | None] | None = None
    direction: Literal["higher", "lower", "mixed", "unchanged"]
    subject_frame_count: int = Field(ge=1)
    comparison_frame_count: int = Field(ge=1)


class RelationSufficiency(BaseModel):
    model_config = ConfigDict(frozen=True)

    gate: Literal["USER_SELECTION_CAN_SUBSTITUTE_STRUCTURE"] = (
        "USER_SELECTION_CAN_SUBSTITUTE_STRUCTURE"
    )
    status: Literal["supported", "experimental", "withhold"]
    reasons: list[str] = Field(default_factory=list)


class BoundarySensitivityHook(BaseModel):
    """Typed attachment point for later locator perturbation/quality analysis."""

    model_config = ConfigDict(frozen=True)

    boundary_provenance: dict[str, Any] = Field(default_factory=dict)
    sensitivity_flags: list[str] = Field(default_factory=list)
    alternate_results: list[dict[str, Any]] = Field(default_factory=list)


class RelationObservation(BaseModel):
    """Small Observation specialization aligned to the #371 conceptual contract."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    kind: Literal["perceptual_span_comparison"] = "perceptual_span_comparison"
    relation_kind: Literal["compare"] = "compare"
    trust_class: Literal["deterministic_derived"] = "deterministic_derived"
    maturity: Literal["production"] = "production"
    subject_locator: SecondsSpanLocator
    comparison_locator: SecondsSpanLocator
    support_refs: list[EvidenceRef] = Field(default_factory=list)
    measurements: list[RelationMeasurement] = Field(default_factory=list)
    sufficiency: RelationSufficiency
    provenance: dict[str, Any] = Field(default_factory=dict)
    sensitivity: BoundarySensitivityHook = Field(default_factory=BoundarySensitivityHook)


def _support_ref(evidence_report_version_id: UUID, feature: str) -> EvidenceRef:
    return EvidenceRef(id=f"{evidence_report_version_id}:{feature}")


def _base_provenance(
    report: PerceptualEvidenceReport,
    evidence_report_version_id: UUID,
) -> dict[str, Any]:
    return {
        "engine": "perceptual_span_compare",
        "engine_version": _RELATION_ENGINE_VERSION,
        "aggregate": "median",
        "source_version_id": str(report.source_version_id),
        "evidence_report_version_id": str(evidence_report_version_id),
        "preprocessing_version": report.preprocessing_version,
        "sample_rate": report.sample_rate,
        "channel_mode": report.channel_mode,
        "coverage_policy": (
            "selected frames must reach both span boundaries within one evidence hop"
        ),
        "relative_denominator_epsilon": _RELATIVE_DENOMINATOR_EPSILON,
        "semantic_interpretation_emitted": False,
    }


def _withheld(
    report: PerceptualEvidenceReport,
    evidence_report_version_id: UUID,
    subject: SecondsSpanLocator,
    comparison: SecondsSpanLocator,
    reasons: Sequence[str],
) -> RelationObservation:
    return RelationObservation(
        subject_locator=subject,
        comparison_locator=comparison,
        support_refs=[],
        measurements=[],
        sufficiency=RelationSufficiency(status="withhold", reasons=list(reasons)),
        provenance=_base_provenance(report, evidence_report_version_id),
    )


def _validate_locator(
    locator: SecondsSpanLocator,
    report: PerceptualEvidenceReport,
    label: str,
) -> list[str]:
    reasons: list[str] = []
    if not math.isfinite(locator.start_seconds) or not math.isfinite(locator.end_seconds):
        reasons.append(f"{label} span boundaries must be finite")
        return reasons
    if locator.start_seconds < 0:
        reasons.append(f"{label} span starts before the source")
    if locator.end_seconds <= locator.start_seconds:
        reasons.append(f"{label} span must have positive duration")
    if locator.end_seconds > report.duration_seconds + _NUMERIC_ATOL:
        reasons.append(f"{label} span ends after the source duration")
    if locator.source_artifact_version_id != report.source_version_id:
        reasons.append(f"{label} span source version does not match the evidence report")
    return reasons


def _series_hop_seconds(series: PerceptualSeriesEvidence) -> float | None:
    hop_length = series.parameters.get("hop_length")
    if hop_length is None:
        hop_length = series.provenance.parameters.get("hop_length")
    if not isinstance(hop_length, int | float) or hop_length <= 0:
        return None
    return float(hop_length) / float(series.sample_rate)


def _series_contract_reasons(
    feature: FeatureName,
    series: PerceptualSeriesEvidence,
    report: PerceptualEvidenceReport,
) -> list[str]:
    reasons: list[str] = []
    if series.source_version_id != report.source_version_id:
        reasons.append(f"{feature} source lineage is incompatible")
    if series.provenance.preprocessing_version != report.preprocessing_version:
        reasons.append(f"{feature} preprocessing version is incompatible")
    if series.sample_rate != report.sample_rate or series.channel_mode != report.channel_mode:
        reasons.append(f"{feature} analysis channel/sample-rate contract is incompatible")
    if series.validated_scope != "within_work_same_preprocessing":
        reasons.append(f"{feature} applicability contract does not allow this comparison")
    if _series_hop_seconds(series) is None:
        reasons.append(f"{feature} is missing a valid hop-length coverage contract")
    return reasons


def _coerce_frame_values(
    feature: FeatureName,
    raw_values: list[float] | list[list[float]],
) -> tuple[FrameValues | None, str | None]:
    if not raw_values:
        return None, f"{feature} has inconsistent or empty evidence"

    first = raw_values[0]
    if isinstance(first, list):
        width = len(first)
        if width == 0:
            return None, f"{feature} has unsupported evidence dimensions"
        rows: list[list[float]] = []
        for raw_row in raw_values:
            if not isinstance(raw_row, list) or len(raw_row) != width:
                return None, f"{feature} has unsupported evidence dimensions"
            row = [float(item) for item in raw_row]
            if not all(math.isfinite(item) for item in row):
                return None, f"{feature} contains non-finite evidence"
            rows.append(row)
        return rows, None

    scalars: list[float] = []
    for raw_value in raw_values:
        if isinstance(raw_value, list):
            return None, f"{feature} has unsupported evidence dimensions"
        value = float(raw_value)
        if not math.isfinite(value):
            return None, f"{feature} contains non-finite evidence"
        scalars.append(value)
    return scalars, None


def _values_for_span(
    feature: FeatureName,
    series: PerceptualSeriesEvidence,
    locator: SecondsSpanLocator,
) -> tuple[FrameValues | None, str | None]:
    times = [float(value) for value in series.frame_times_seconds]
    if not times or len(times) != len(series.values):
        return None, f"{feature} has inconsistent or empty evidence"
    if not all(math.isfinite(value) for value in times):
        return None, f"{feature} contains non-finite evidence"
    if any(current < previous for previous, current in zip(times, times[1:], strict=False)):
        return None, f"{feature} frame times are not monotonic"

    values, values_error = _coerce_frame_values(feature, series.values)
    if values_error is not None or values is None:
        return None, values_error

    selected_indexes = [
        index
        for index, frame_time in enumerate(times)
        if locator.start_seconds <= frame_time <= locator.end_seconds
    ]
    if not selected_indexes:
        return None, f"{feature} does not cover the requested span"

    selected_times = [times[index] for index in selected_indexes]
    hop_seconds = _series_hop_seconds(series)
    if hop_seconds is None:
        return None, f"{feature} is missing a valid hop-length coverage contract"
    boundary_tolerance = hop_seconds + _NUMERIC_ATOL
    if selected_times[0] - locator.start_seconds > boundary_tolerance:
        return None, f"{feature} does not cover the span start within one evidence hop"
    if locator.end_seconds - selected_times[-1] > boundary_tolerance:
        return None, f"{feature} does not cover the span end within one evidence hop"

    return [values[index] for index in selected_indexes], None


def _median(values: FrameValues) -> Numeric:
    first = values[0]
    if isinstance(first, list):
        rows = [row for row in values if isinstance(row, list)]
        width = len(first)
        return [float(median(row[column] for row in rows)) for column in range(width)]
    return float(median(float(value) for value in values if not isinstance(value, list)))


def _subtract(subject: Numeric, comparison: Numeric) -> Numeric:
    if isinstance(subject, list) and isinstance(comparison, list):
        return [left - right for left, right in zip(subject, comparison, strict=True)]
    if isinstance(subject, list) or isinstance(comparison, list):
        raise ValueError("cannot compare scalar and vector aggregates")
    return subject - comparison


def _direction(delta: Numeric) -> Literal["higher", "lower", "mixed", "unchanged"]:
    values = delta if isinstance(delta, list) else [delta]
    nonzero = [
        value
        for value in values
        if not math.isclose(value, 0.0, abs_tol=_NUMERIC_ATOL, rel_tol=_NUMERIC_RTOL)
    ]
    if not nonzero:
        return "unchanged"
    if all(value > 0 for value in nonzero):
        return "higher"
    if all(value < 0 for value in nonzero):
        return "lower"
    return "mixed"


def _relative_delta(
    delta: Numeric,
    comparison: Numeric,
) -> float | list[float | None] | None:
    if isinstance(delta, list) and isinstance(comparison, list):
        result: list[float | None] = []
        for item_delta, item_comparison in zip(delta, comparison, strict=True):
            denominator = abs(item_comparison)
            if denominator <= _RELATIVE_DENOMINATOR_EPSILON:
                result.append(None)
            else:
                result.append(float(item_delta / denominator))
        return result
    if isinstance(delta, list) or isinstance(comparison, list):
        raise ValueError("cannot compare scalar and vector aggregates")
    denominator = abs(comparison)
    if denominator <= _RELATIVE_DENOMINATOR_EPSILON:
        return None
    return float(delta / denominator)


def _components(series: PerceptualSeriesEvidence) -> list[str]:
    band_order = series.parameters.get("band_order")
    if not isinstance(band_order, list):
        return []
    return [str(item) for item in band_order]


def compare_perceptual_spans(
    report: PerceptualEvidenceReport,
    *,
    evidence_report_version_id: UUID,
    subject_locator: SecondsSpanLocator,
    comparison_locator: SecondsSpanLocator,
    features: Sequence[FeatureName] = _SUPPORTED_FEATURES,
) -> RelationObservation:
    """Compare promoted perceptual evidence across two explicit source spans.

    The function returns a withhold observation for invalid/incompatible evidence so
    callers never need a hidden fallback path. Programming/type errors still raise
    normally through Pydantic/Python.
    """

    reasons = [
        *_validate_locator(subject_locator, report, "subject"),
        *_validate_locator(comparison_locator, report, "comparison"),
    ]
    requested = list(features)
    if not requested:
        reasons.append("at least one promoted perceptual feature is required")
    if len(set(requested)) != len(requested):
        reasons.append("perceptual comparison features must be unique")
    unsupported = sorted(set(requested) - set(_SUPPORTED_FEATURES))
    if unsupported:
        reasons.append(f"unsupported perceptual comparison features: {unsupported}")
    if reasons:
        return _withheld(
            report,
            evidence_report_version_id,
            subject_locator,
            comparison_locator,
            reasons,
        )

    measurements: list[RelationMeasurement] = []
    support_refs: list[EvidenceRef] = []
    for feature in requested:
        series = report.series.get(feature)
        if series is None:
            reasons.append(f"required perceptual evidence is missing: {feature}")
            continue
        reasons.extend(_series_contract_reasons(feature, series, report))
        subject_values, subject_error = _values_for_span(feature, series, subject_locator)
        comparison_values, comparison_error = _values_for_span(feature, series, comparison_locator)
        if subject_error:
            reasons.append(f"subject: {subject_error}")
        if comparison_error:
            reasons.append(f"comparison: {comparison_error}")
        if subject_values is None or comparison_values is None:
            continue

        subject_aggregate = _median(subject_values)
        comparison_aggregate = _median(comparison_values)
        delta = _subtract(subject_aggregate, comparison_aggregate)
        delta_values = delta if isinstance(delta, list) else [delta]
        if not all(math.isfinite(value) for value in delta_values):
            reasons.append(f"{feature} aggregate delta is non-finite")
            continue

        measurements.append(
            RelationMeasurement(
                feature=feature,
                unit=series.unit,
                normalization=series.normalization,
                components=_components(series),
                subject_value=subject_aggregate,
                comparison_value=comparison_aggregate,
                delta=delta,
                relative_delta=_relative_delta(delta, comparison_aggregate),
                direction=_direction(delta),
                subject_frame_count=len(subject_values),
                comparison_frame_count=len(comparison_values),
            )
        )
        support_refs.append(_support_ref(evidence_report_version_id, feature))

    if reasons or len(measurements) != len(requested):
        return _withheld(
            report,
            evidence_report_version_id,
            subject_locator,
            comparison_locator,
            reasons or ["not all requested evidence produced a valid measurement"],
        )

    return RelationObservation(
        subject_locator=subject_locator,
        comparison_locator=comparison_locator,
        support_refs=support_refs,
        measurements=measurements,
        sufficiency=RelationSufficiency(status="supported"),
        provenance=_base_provenance(report, evidence_report_version_id),
    )


__all__ = [
    "BoundarySensitivityHook",
    "EvidenceRef",
    "RelationMeasurement",
    "RelationObservation",
    "RelationSufficiency",
    "SecondsSpanLocator",
    "compare_perceptual_spans",
]

"""Deterministic relation observations over promoted measured evidence.

The first M2 relation is deliberately narrow: compare two explicit seconds spans
inside one canonical :class:`PerceptualEvidenceReport`. It emits literal numeric
relations only and withholds on incompatible lineage, preprocessing, coverage, or
values instead of falling back to weaker evidence or semantic interpretation.
"""

from __future__ import annotations

import math
from typing import Any, Literal, Sequence
from uuid import UUID, uuid4

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from perceptual_evidence import FeatureName, PerceptualEvidenceReport, PerceptualSeriesEvidence

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
        "coverage_policy": "selected frames must reach both span boundaries within one evidence hop",
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
    if not isinstance(hop_length, (int, float)) or hop_length <= 0:
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


def _values_for_span(
    feature: FeatureName,
    series: PerceptualSeriesEvidence,
    locator: SecondsSpanLocator,
) -> tuple[np.ndarray | None, str | None]:
    times = np.asarray(series.frame_times_seconds, dtype=float)
    values = np.asarray(series.values, dtype=float)
    if times.ndim != 1 or values.ndim not in {1, 2}:
        return None, f"{feature} has unsupported evidence dimensions"
    if len(times) != len(values) or len(times) == 0:
        return None, f"{feature} has inconsistent or empty evidence"
    if not np.isfinite(times).all() or not np.isfinite(values).all():
        return None, f"{feature} contains non-finite evidence"
    if np.any(np.diff(times) < 0):
        return None, f"{feature} frame times are not monotonic"

    mask = np.logical_and(
        times >= locator.start_seconds,
        times <= locator.end_seconds,
    )
    if not np.any(mask):
        return None, f"{feature} does not cover the requested span"

    selected_times = times[mask]
    hop_seconds = _series_hop_seconds(series)
    if hop_seconds is None:
        return None, f"{feature} is missing a valid hop-length coverage contract"
    boundary_tolerance = hop_seconds + _NUMERIC_ATOL
    if selected_times[0] - locator.start_seconds > boundary_tolerance:
        return None, f"{feature} does not cover the span start within one evidence hop"
    if locator.end_seconds - selected_times[-1] > boundary_tolerance:
        return None, f"{feature} does not cover the span end within one evidence hop"

    return values[mask], None


def _median(values: np.ndarray) -> float | np.ndarray:
    result = np.median(values, axis=0)
    if np.ndim(result) == 0:
        return float(result)
    return np.asarray(result, dtype=float)


def _direction(delta: float | np.ndarray) -> Literal["higher", "lower", "mixed", "unchanged"]:
    array = np.asarray(delta, dtype=float)
    close = np.isclose(array, 0.0, atol=_NUMERIC_ATOL, rtol=_NUMERIC_RTOL)
    if bool(np.all(close)):
        return "unchanged"
    nonzero = array[~close]
    if bool(np.all(nonzero > 0)):
        return "higher"
    if bool(np.all(nonzero < 0)):
        return "lower"
    return "mixed"


def _serialize_numeric(value: float | np.ndarray) -> float | list[float]:
    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        return float(array)
    return array.tolist()


def _relative_delta(
    delta: float | np.ndarray,
    comparison: float | np.ndarray,
) -> float | list[float | None] | None:
    delta_array = np.asarray(delta, dtype=float)
    comparison_array = np.asarray(comparison, dtype=float)
    denominator = np.abs(comparison_array)

    if delta_array.ndim == 0:
        if float(denominator) <= _RELATIVE_DENOMINATOR_EPSILON:
            return None
        return float(delta_array / denominator)

    result: list[float | None] = []
    for item_delta, item_denominator in zip(
        delta_array.tolist(), denominator.tolist(), strict=True
    ):
        if item_denominator <= _RELATIVE_DENOMINATOR_EPSILON:
            result.append(None)
        else:
            result.append(float(item_delta / item_denominator))
    return result


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
        comparison_values, comparison_error = _values_for_span(
            feature, series, comparison_locator
        )
        if subject_error:
            reasons.append(f"subject: {subject_error}")
        if comparison_error:
            reasons.append(f"comparison: {comparison_error}")
        if subject_values is None or comparison_values is None:
            continue

        subject_aggregate = _median(subject_values)
        comparison_aggregate = _median(comparison_values)
        delta = np.asarray(subject_aggregate) - np.asarray(comparison_aggregate)
        if not np.isfinite(delta).all():
            reasons.append(f"{feature} aggregate delta is non-finite")
            continue

        measurements.append(
            RelationMeasurement(
                feature=feature,
                unit=series.unit,
                normalization=series.normalization,
                components=_components(series),
                subject_value=_serialize_numeric(subject_aggregate),
                comparison_value=_serialize_numeric(comparison_aggregate),
                delta=_serialize_numeric(delta),
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

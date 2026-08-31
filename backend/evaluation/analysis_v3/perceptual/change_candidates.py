"""Evaluation-only candidate discovery for measured within-Work change moments.

The production relation layer already owns truthful A/B span comparison over a
persisted :class:`PerceptualEvidenceReport`. This module intentionally adds only
the missing discovery question for #848: which boundaries are worth comparing?

Candidates are ranked from six gain-independent dimensions already promoted by
``perceptual_series``. Returned before/after measurements are delegated to the
production ``compare_perceptual_spans`` contract so this probe cannot grow a
second relation/evidence semantics layer.
"""

from __future__ import annotations

import math
from typing import Literal
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.signal import find_peaks

from domain.perceptual_report import PerceptualEvidenceReport, PerceptualSeriesEvidence
from domain.relation_observations import (
    RelationObservation,
    SecondsSpanLocator,
    compare_perceptual_spans,
)

_METHOD = "robust_before_after_median_v1"
_BAND_ORDER = ("low", "low_mid", "mid", "high")
_SCORE_FEATURES = ("onset_strength", "spectral_centroid", "relative_band_energy")
_EPSILON = 1e-9


class MeasuredChangeCandidate(BaseModel):
    """One evaluation candidate plus its production-owned literal A/B relation."""

    model_config = ConfigDict(frozen=True)

    boundary_seconds: float
    before_span_seconds: tuple[float, float]
    after_span_seconds: tuple[float, float]
    score: float
    score_threshold: float
    component_scores: dict[str, float] = Field(default_factory=dict)
    observation: RelationObservation


class ChangeDiscoveryResult(BaseModel):
    """Fail-closed result for the evaluation-only discovery control."""

    model_config = ConfigDict(frozen=True)

    status: Literal["supported", "withheld"]
    method: Literal["robust_before_after_median_v1"] = _METHOD
    method_parameters: dict[str, float | int] = Field(default_factory=dict)
    candidates: list[MeasuredChangeCandidate] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


def _withheld(reason: str, **parameters: float | int) -> ChangeDiscoveryResult:
    return ChangeDiscoveryResult(
        status="withheld",
        method_parameters=parameters,
        reasons=[reason],
    )


def _series_values(
    series: PerceptualSeriesEvidence,
    *,
    expected_width: int,
) -> np.ndarray | None:
    values = np.asarray(series.values, dtype=float)
    if expected_width == 1:
        if values.ndim != 1:
            return None
        values = values[:, np.newaxis]
    elif values.ndim != 2 or values.shape[1] != expected_width:
        return None
    if values.size == 0 or not np.isfinite(values).all():
        return None
    return values


def _validated_matrix(
    report: PerceptualEvidenceReport,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    reasons: list[str] = []
    onset = report.series.get("onset_strength")
    centroid = report.series.get("spectral_centroid")
    bands = report.series.get("relative_band_energy")
    if onset is None or centroid is None or bands is None:
        return np.array([]), np.empty((0, 6)), [
            "required gain-independent perceptual evidence is missing"
        ]

    series_items = (
        ("onset_strength", onset),
        ("spectral_centroid", centroid),
        ("relative_band_energy", bands),
    )
    reference_times = [float(value) for value in onset.frame_times_seconds]
    if not reference_times or not all(math.isfinite(value) for value in reference_times):
        reasons.append("onset-strength frame grid is empty or non-finite")
    elif any(
        current <= previous
        for previous, current in zip(reference_times, reference_times[1:], strict=False)
    ):
        reasons.append("perceptual frame grid must be strictly increasing")

    for feature, series in series_items:
        if series.source_version_id != report.source_version_id:
            reasons.append(f"{feature} source Version does not match the report")
        if series.provenance.preprocessing_version != report.preprocessing_version:
            reasons.append(f"{feature} preprocessing does not match the report")
        if series.sample_rate != report.sample_rate or series.channel_mode != report.channel_mode:
            reasons.append(f"{feature} sample-rate/channel contract is incompatible")
        if series.validated_scope != "within_work_same_preprocessing":
            reasons.append(f"{feature} is outside its validated comparison scope")
        times = [float(value) for value in series.frame_times_seconds]
        if times != reference_times:
            reasons.append(f"{feature} does not share the exact promoted frame grid")

    band_order = bands.parameters.get("band_order")
    if band_order != list(_BAND_ORDER):
        reasons.append("relative-band evidence does not use the expected four-band order")

    onset_values = _series_values(onset, expected_width=1)
    centroid_values = _series_values(centroid, expected_width=1)
    band_values = _series_values(bands, expected_width=4)
    if onset_values is None:
        reasons.append("onset-strength values are empty, non-finite, or malformed")
    if centroid_values is None:
        reasons.append("spectral-centroid values are empty, non-finite, or malformed")
    if band_values is None:
        reasons.append("relative-band values are empty, non-finite, or malformed")
    if reasons or onset_values is None or centroid_values is None or band_values is None:
        return np.array([]), np.empty((0, 6)), reasons

    matrix = np.concatenate([onset_values, centroid_values, band_values], axis=1)
    if matrix.shape[0] != len(reference_times):
        return np.array([]), np.empty((0, 6)), [
            "promoted perceptual evidence lengths are inconsistent"
        ]
    return np.asarray(reference_times, dtype=float), matrix, []


def _robust_standardize(matrix: np.ndarray) -> np.ndarray:
    center = np.median(matrix, axis=0)
    mad = np.median(np.abs(matrix - center), axis=0)
    scale = 1.4826 * mad
    standard = np.std(matrix, axis=0)
    scale = np.where(scale > _EPSILON, scale, standard)
    scale = np.where(scale > _EPSILON, scale, 1.0)
    return (matrix - center) / scale


def _score_boundaries(
    times: np.ndarray,
    normalized: np.ndarray,
    *,
    window_seconds: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    boundary_times: list[float] = []
    scores: list[float] = []
    component_scores: list[np.ndarray] = []
    for boundary in times:
        if boundary < window_seconds or boundary + window_seconds > times[-1]:
            continue
        before_mask = np.logical_and(times >= boundary - window_seconds, times < boundary)
        after_mask = np.logical_and(times >= boundary, times < boundary + window_seconds)
        if not np.any(before_mask) or not np.any(after_mask):
            continue
        before = np.median(normalized[before_mask], axis=0)
        after = np.median(normalized[after_mask], axis=0)
        delta = after - before
        if not np.isfinite(delta).all():
            continue
        boundary_times.append(float(boundary))
        component_scores.append(np.abs(delta))
        scores.append(float(np.sqrt(np.mean(np.square(delta)))))
    if not boundary_times:
        return np.array([]), np.array([]), np.empty((0, 6))
    return np.asarray(boundary_times), np.asarray(scores), np.vstack(component_scores)


def _score_threshold(scores: np.ndarray, threshold_mad: float) -> tuple[float, float]:
    center = float(np.median(scores))
    mad = float(np.median(np.abs(scores - center)))
    robust_sigma = 1.4826 * mad
    if robust_sigma <= _EPSILON:
        nonzero = scores[scores > center + _EPSILON]
        if nonzero.size == 0:
            return center + _EPSILON, 0.0
        robust_sigma = float(np.std(nonzero))
    return center + threshold_mad * max(robust_sigma, _EPSILON), robust_sigma


def discover_measured_change_candidates(
    report: PerceptualEvidenceReport,
    *,
    evidence_report_version_id: UUID,
    window_seconds: float = 4.0,
    min_separation_seconds: float = 4.0,
    threshold_mad: float = 3.0,
    max_candidates: int = 8,
) -> ChangeDiscoveryResult:
    """Discover a small set of literal before/after change candidates.

    The aggregate score is a within-Work ranking value only. It is never a
    calibrated confidence, significance, structural-boundary probability, or
    cross-song score.
    """

    parameters: dict[str, float | int] = {
        "window_seconds": window_seconds,
        "min_separation_seconds": min_separation_seconds,
        "threshold_mad": threshold_mad,
        "max_candidates": max_candidates,
    }
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        return _withheld("window_seconds must be positive and finite", **parameters)
    if not math.isfinite(min_separation_seconds) or min_separation_seconds <= 0:
        return _withheld("min_separation_seconds must be positive and finite", **parameters)
    if not math.isfinite(threshold_mad) or threshold_mad < 0:
        return _withheld("threshold_mad must be finite and non-negative", **parameters)
    if max_candidates <= 0:
        return _withheld("max_candidates must be positive", **parameters)

    times, matrix, reasons = _validated_matrix(report)
    if reasons:
        return ChangeDiscoveryResult(
            status="withheld",
            method_parameters=parameters,
            reasons=reasons,
        )
    if times.size < 3 or report.duration_seconds < 2 * window_seconds:
        return _withheld("evidence is too short for the requested before/after windows", **parameters)

    normalized = _robust_standardize(matrix)
    boundary_times, scores, components = _score_boundaries(
        times,
        normalized,
        window_seconds=window_seconds,
    )
    if scores.size == 0:
        return _withheld("no complete before/after boundary windows are available", **parameters)

    threshold, robust_sigma = _score_threshold(scores, threshold_mad)
    if boundary_times.size > 1:
        candidate_step = float(np.median(np.diff(boundary_times)))
    else:
        candidate_step = min_separation_seconds
    peak_distance = max(1, int(math.ceil(min_separation_seconds / candidate_step)))
    prominence = max(robust_sigma, _EPSILON)
    peaks, properties = find_peaks(
        scores,
        height=threshold,
        distance=peak_distance,
        prominence=prominence,
    )
    if peaks.size == 0:
        return ChangeDiscoveryResult(status="supported", method_parameters=parameters)

    peak_heights = np.asarray(properties["peak_heights"], dtype=float)
    ordered = sorted(
        zip(peaks.tolist(), peak_heights.tolist(), strict=True),
        key=lambda item: (-item[1], float(boundary_times[item[0]])),
    )[:max_candidates]

    names = ("onset_strength", "spectral_centroid", *_BAND_ORDER)
    candidates: list[MeasuredChangeCandidate] = []
    for index, score in ordered:
        boundary = float(boundary_times[index])
        before_span = (boundary - window_seconds, boundary)
        after_span = (boundary, boundary + window_seconds)
        observation = compare_perceptual_spans(
            report,
            evidence_report_version_id=evidence_report_version_id,
            subject_locator=SecondsSpanLocator(
                start_seconds=before_span[0],
                end_seconds=before_span[1],
                source_artifact_version_id=report.source_version_id,
                authority="trusted",
            ),
            comparison_locator=SecondsSpanLocator(
                start_seconds=after_span[0],
                end_seconds=after_span[1],
                source_artifact_version_id=report.source_version_id,
                authority="trusted",
            ),
            features=_SCORE_FEATURES,
        )
        if observation.sufficiency.status != "supported":
            continue
        candidates.append(
            MeasuredChangeCandidate(
                boundary_seconds=boundary,
                before_span_seconds=before_span,
                after_span_seconds=after_span,
                score=float(score),
                score_threshold=float(threshold),
                component_scores={
                    name: float(value)
                    for name, value in zip(names, components[index], strict=True)
                },
                observation=observation,
            )
        )

    return ChangeDiscoveryResult(
        status="supported",
        method_parameters=parameters,
        candidates=candidates,
    )


__all__ = [
    "ChangeDiscoveryResult",
    "MeasuredChangeCandidate",
    "discover_measured_change_candidates",
]

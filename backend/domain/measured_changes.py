"""Experimental measured-change discovery over promoted perceptual evidence.

This module owns only candidate proposal/ranking. Literal before/after evidence,
coverage, source lineage, support refs, and product-facing measurement copy remain
owned by the production perceptual span-comparison contract.

The method is deliberately qualified: a returned candidate means that multiple
declared measured features changed around this time under this method. It does
not assert a section boundary, drop, climax, transition importance, or emotion.
"""

from __future__ import annotations

import math
from typing import Literal
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.signal import find_peaks

from domain.perceptual_report import PerceptualEvidenceReport, PerceptualSeriesEvidence
from domain.relation_findings import GroundedRelationFinding, compose_grounded_relation_finding
from domain.relation_observations import SecondsSpanLocator, compare_perceptual_spans

_METHOD = "robust_top_peaks_v1"
_BAND_ORDER = ("low", "low_mid", "mid", "high")
_SCORE_FEATURES = ("onset_strength", "spectral_centroid", "relative_band_energy")
_COMPONENT_NAMES = ("onset_strength", "spectral_centroid", *_BAND_ORDER)
_EPSILON = 1e-9


class MeasuredChangeCandidate(BaseModel):
    """One bounded experimental candidate with production-owned literal evidence."""

    model_config = ConfigDict(frozen=True)

    rank: int = Field(ge=1)
    boundary_seconds: float
    before_span_seconds: tuple[float, float]
    after_span_seconds: tuple[float, float]
    ranking_score: float
    changed_feature_count: int = Field(ge=2, le=3)
    changed_component_count: int = Field(ge=2, le=6)
    normalized_feature_changes: dict[str, float] = Field(default_factory=dict)
    normalized_component_changes: dict[str, float] = Field(default_factory=dict)
    finding: GroundedRelationFinding


class MeasuredChangeDiscovery(BaseModel):
    """Fail-closed result for the experimental discovery method."""

    model_config = ConfigDict(frozen=True)

    status: Literal["supported", "withheld"]
    method: Literal["robust_top_peaks_v1"] = _METHOD
    method_parameters: dict[str, float | int] = Field(default_factory=dict)
    candidates: list[MeasuredChangeCandidate] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


def _withheld(reason: str, **parameters: float | int) -> MeasuredChangeDiscovery:
    return MeasuredChangeDiscovery(
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
    """Reuse #883's valid evidence-matrix contract without its rejected threshold."""

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

    if bands.parameters.get("band_order") != list(_BAND_ORDER):
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
    component_changes: list[np.ndarray] = []
    for boundary in times:
        if boundary < window_seconds or boundary + window_seconds > times[-1]:
            continue
        before_mask = np.logical_and(times >= boundary - window_seconds, times < boundary)
        after_mask = np.logical_and(times >= boundary, times < boundary + window_seconds)
        if not np.any(before_mask) or not np.any(after_mask):
            continue
        before = np.median(normalized[before_mask], axis=0)
        after = np.median(normalized[after_mask], axis=0)
        delta = np.abs(after - before)
        if not np.isfinite(delta).all():
            continue
        boundary_times.append(float(boundary))
        component_changes.append(delta)
        scores.append(float(np.sqrt(np.mean(np.square(delta)))))
    if not boundary_times:
        return np.array([]), np.array([]), np.empty((0, 6))
    return np.asarray(boundary_times), np.asarray(scores), np.vstack(component_changes)


def _feature_changes(component_changes: np.ndarray) -> dict[str, float]:
    """Collapse four band components into one declared feature-group change."""

    return {
        "onset_strength": float(component_changes[0]),
        "spectral_centroid": float(component_changes[1]),
        "relative_band_energy": float(
            np.sqrt(np.mean(np.square(component_changes[2:])))
        ),
    }


def discover_measured_changes(
    report: PerceptualEvidenceReport,
    *,
    evidence_report_version_id: UUID,
    window_seconds: float = 4.0,
    min_separation_seconds: float = 8.0,
    feature_change_floor: float = 0.5,
    min_changed_features: int = 2,
    max_candidates: int = 5,
) -> MeasuredChangeDiscovery:
    """Return a small, deterministic top set of measured before/after changes.

    #883 showed that the previous robust-threshold local-peak control could miss
    obvious changes and that PELT could become an overcomplete proposal stream.
    This experimental method keeps the valid robust before/after score, removes
    the brittle global threshold, requires multiple declared feature groups to
    move, then applies deterministic local-peak separation and a hard top-set cap.

    ``ranking_score`` and normalized change magnitudes are method-internal,
    within-Work ranking values. They are not confidence, significance,
    importance, semantic-boundary probability, or cross-Work comparable.
    """

    parameters: dict[str, float | int] = {
        "window_seconds": window_seconds,
        "min_separation_seconds": min_separation_seconds,
        "feature_change_floor": feature_change_floor,
        "min_changed_features": min_changed_features,
        "max_candidates": max_candidates,
    }
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        return _withheld("window_seconds must be positive and finite", **parameters)
    if not math.isfinite(min_separation_seconds) or min_separation_seconds <= 0:
        return _withheld("min_separation_seconds must be positive and finite", **parameters)
    if not math.isfinite(feature_change_floor) or feature_change_floor <= 0:
        return _withheld("feature_change_floor must be positive and finite", **parameters)
    if not 2 <= min_changed_features <= 3:
        return _withheld("min_changed_features must be between 2 and 3", **parameters)
    if max_candidates <= 0:
        return _withheld("max_candidates must be positive", **parameters)

    times, matrix, reasons = _validated_matrix(report)
    if reasons:
        return MeasuredChangeDiscovery(
            status="withheld",
            method_parameters=parameters,
            reasons=reasons,
        )
    if times.size < 3 or report.duration_seconds < 2 * window_seconds:
        return _withheld("evidence is too short for the requested before/after windows", **parameters)

    normalized = _robust_standardize(matrix)
    boundary_times, scores, component_changes = _score_boundaries(
        times,
        normalized,
        window_seconds=window_seconds,
    )
    if scores.size == 0:
        return _withheld("no complete before/after boundary windows are available", **parameters)

    if boundary_times.size > 1:
        candidate_step = float(np.median(np.diff(boundary_times)))
    else:
        candidate_step = min_separation_seconds
    peak_distance = max(1, int(math.ceil(min_separation_seconds / candidate_step)))
    peaks, _ = find_peaks(scores, distance=peak_distance)
    feature_changes_by_index = {
        index: _feature_changes(component_changes[index]) for index in peaks.tolist()
    }
    eligible = [
        index
        for index in peaks.tolist()
        if sum(
            value >= feature_change_floor
            for value in feature_changes_by_index[index].values()
        )
        >= min_changed_features
    ]
    ordered = sorted(
        eligible,
        key=lambda index: (-float(scores[index]), float(boundary_times[index])),
    )[:max_candidates]

    candidates: list[MeasuredChangeCandidate] = []
    for index in ordered:
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
        finding = compose_grounded_relation_finding(observation)
        if finding is None:
            continue
        changes = component_changes[index]
        feature_changes = feature_changes_by_index[index]
        changed_feature_count = sum(
            value >= feature_change_floor for value in feature_changes.values()
        )
        changed_component_count = int(np.count_nonzero(changes >= feature_change_floor))
        candidates.append(
            MeasuredChangeCandidate(
                rank=len(candidates) + 1,
                boundary_seconds=boundary,
                before_span_seconds=before_span,
                after_span_seconds=after_span,
                ranking_score=float(scores[index]),
                changed_feature_count=changed_feature_count,
                changed_component_count=changed_component_count,
                normalized_feature_changes=feature_changes,
                normalized_component_changes={
                    name: float(value)
                    for name, value in zip(_COMPONENT_NAMES, changes, strict=True)
                },
                finding=finding,
            )
        )

    return MeasuredChangeDiscovery(
        status="supported",
        method_parameters=parameters,
        candidates=candidates,
    )


__all__ = [
    "MeasuredChangeCandidate",
    "MeasuredChangeDiscovery",
    "discover_measured_changes",
]

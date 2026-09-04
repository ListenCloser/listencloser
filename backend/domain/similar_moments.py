"""Experimental same-Work similar-moment proposals over promoted perceptual evidence.

The matcher intentionally reuses the fixed descriptor representation explored by
#822, but exposes it with a narrower product truth contract: a returned passage
is only close to the selected passage under this declared method. It is not a
motif, chorus, section, melody, or semantic-identity detector.
"""

from __future__ import annotations

from math import sqrt
from typing import Literal
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from domain.perceptual_report import PerceptualEvidenceReport

SIMILAR_MOMENTS_METHOD_ID = "perceptual_descriptor_shape"
SIMILAR_MOMENTS_METHOD_VERSION = "1.0"
RECURRENCE_DIMENSIONS: tuple[str, ...] = (
    "onset_strength",
    "spectral_centroid",
    "band_low",
    "band_low_mid",
    "band_mid",
    "band_high",
)
EXPECTED_BAND_ORDER = ("low", "low_mid", "mid", "high")
CONSTANT_STD_THRESHOLD = 1e-8
MIN_QUERY_FRAMES = 4
DEFAULT_MAX_MATCHES = 3
MAX_MATCHES = 5
_NUMERIC_ATOL = 1e-9


class SimilarMomentMatch(BaseModel):
    """One inspectable candidate under the declared descriptor-shape method."""

    model_config = ConfigDict(frozen=True)

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    distance: float = Field(ge=0)
    component_distances: dict[str, float]


class SimilarMomentsMethod(BaseModel):
    """Stable declaration of what the experimental distance does and does not mean."""

    model_config = ConfigDict(frozen=True)

    id: Literal["perceptual_descriptor_shape"] = SIMILAR_MOMENTS_METHOD_ID
    version: Literal["1.0"] = SIMILAR_MOMENTS_METHOD_VERSION
    dimensions: list[str] = Field(default_factory=lambda: list(RECURRENCE_DIMENSIONS))
    distance: Literal["mean_length_normalized_z_euclidean"] = (
        "mean_length_normalized_z_euclidean"
    )
    candidate_window: Literal["same_evidence_frame_count_as_query"] = (
        "same_evidence_frame_count_as_query"
    )
    overlap_exclusion: Literal[
        "exclude_query_overlap_and_mutually_overlapping_returned_windows"
    ] = "exclude_query_overlap_and_mutually_overlapping_returned_windows"
    score_semantics: Literal["lower_is_closer_under_this_method_not_confidence"] = (
        "lower_is_closer_under_this_method_not_confidence"
    )
    semantic_claims: Literal["none"] = "none"
    parameters: dict[str, float | int] = Field(default_factory=dict)


class SimilarMomentsObservation(BaseModel):
    """Experimental result tied to one exact source/evidence Version pair."""

    model_config = ConfigDict(frozen=True)

    source_version_id: UUID
    evidence_report_version_id: UUID
    evidence_report_type: Literal["perceptual_series"] = "perceptual_series"
    preprocessing_version: str
    sample_rate: int
    query_start_seconds: float = Field(ge=0)
    query_end_seconds: float = Field(gt=0)
    max_matches: int = Field(ge=1, le=MAX_MATCHES)
    method: SimilarMomentsMethod
    matches: list[SimilarMomentMatch] = Field(default_factory=list)
    no_match_reason: str | None = None


class _FixedPerceptualMatrix(BaseModel):
    """Six gain-independent descriptor trajectories on one exact evidence grid."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    source_version_id: UUID
    frame_times_seconds: np.ndarray
    values: np.ndarray


def _as_scalar_series(
    values: list[float] | list[list[float]],
    *,
    feature: str,
) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{feature} must be a scalar frame series")
    return array


def _build_fixed_perceptual_matrix(report: PerceptualEvidenceReport) -> _FixedPerceptualMatrix:
    required = {"onset_strength", "spectral_centroid", "relative_band_energy"}
    missing = required.difference(report.series)
    if missing:
        raise ValueError(f"missing required similar-moments evidence: {sorted(missing)}")

    onset = report.series["onset_strength"]
    centroid = report.series["spectral_centroid"]
    bands = report.series["relative_band_energy"]
    selected = (onset, centroid, bands)

    for series in selected:
        if series.source_version_id != report.source_version_id:
            raise ValueError("similar-moments evidence must share one source Version")
        if series.provenance.preprocessing_version != report.preprocessing_version:
            raise ValueError("similar-moments evidence preprocessing must match the report")
        if series.channel_mode != report.channel_mode or series.sample_rate != report.sample_rate:
            raise ValueError("similar-moments evidence channel/sample-rate contract is incompatible")
        if series.validated_scope != "within_work_same_preprocessing":
            raise ValueError("similar-moments evidence applicability contract is incompatible")

    times = np.asarray(onset.frame_times_seconds, dtype=float)
    if times.ndim != 1 or len(times) < MIN_QUERY_FRAMES:
        raise ValueError("similar-moments evidence has too few frames")
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("similar-moments frame times must be finite and strictly increasing")

    for series in (centroid, bands):
        other_times = np.asarray(series.frame_times_seconds, dtype=float)
        if len(other_times) != len(times) or not np.allclose(
            other_times,
            times,
            rtol=0.0,
            atol=_NUMERIC_ATOL,
        ):
            raise ValueError("similar-moments evidence dimensions must share one exact frame grid")

    onset_values = _as_scalar_series(onset.values, feature="onset_strength")
    centroid_values = _as_scalar_series(centroid.values, feature="spectral_centroid")
    band_values = np.asarray(bands.values, dtype=float)
    if band_values.ndim != 2 or band_values.shape != (len(times), 4):
        raise ValueError("relative_band_energy must contain exactly four values per frame")

    band_order = tuple(bands.parameters.get("band_order", ()))
    if band_order != EXPECTED_BAND_ORDER:
        raise ValueError(
            "relative_band_energy band_order must be "
            f"{EXPECTED_BAND_ORDER}, got {band_order}"
        )

    values = np.vstack(
        (
            onset_values,
            centroid_values,
            band_values[:, 0],
            band_values[:, 1],
            band_values[:, 2],
            band_values[:, 3],
        )
    )
    if values.shape != (len(RECURRENCE_DIMENSIONS), len(times)):
        raise ValueError("unexpected similar-moments matrix shape")
    if not np.isfinite(values).all():
        raise ValueError("similar-moments evidence must contain only finite values")

    return _FixedPerceptualMatrix(
        source_version_id=report.source_version_id,
        frame_times_seconds=times,
        values=values,
    )


def _normalized_component_distance(query: np.ndarray, candidate: np.ndarray) -> float:
    """Length-normalized z-Euclidean distance with explicit constant semantics."""

    if query.shape != candidate.shape or query.ndim != 1 or query.size == 0:
        raise ValueError("query and candidate must be equal non-empty 1D windows")

    query_std = float(np.std(query))
    candidate_std = float(np.std(candidate))
    query_constant = query_std < CONSTANT_STD_THRESHOLD
    candidate_constant = candidate_std < CONSTANT_STD_THRESHOLD

    if query_constant and candidate_constant:
        return 0.0
    if query_constant != candidate_constant:
        return 1.0

    query_z = (query - float(np.mean(query))) / query_std
    candidate_z = (candidate - float(np.mean(candidate))) / candidate_std
    return float(np.linalg.norm(query_z - candidate_z) / sqrt(query.size))


def _distance_profile(
    matrix: _FixedPerceptualMatrix,
    *,
    query_start_frame: int,
    window_frames: int,
) -> tuple[np.ndarray, np.ndarray]:
    if query_start_frame < 0 or window_frames < MIN_QUERY_FRAMES:
        raise ValueError("invalid similar-moments query frame range")
    query_end = query_start_frame + window_frames
    if query_end > matrix.values.shape[1]:
        raise ValueError("similar-moments query exceeds available evidence")

    candidate_count = matrix.values.shape[1] - window_frames + 1
    component_profiles = np.empty(
        (candidate_count, len(RECURRENCE_DIMENSIONS)),
        dtype=float,
    )
    query = matrix.values[:, query_start_frame:query_end]

    for candidate_start in range(candidate_count):
        candidate = matrix.values[:, candidate_start : candidate_start + window_frames]
        for dimension_index in range(len(RECURRENCE_DIMENSIONS)):
            component_profiles[candidate_start, dimension_index] = (
                _normalized_component_distance(
                    query[dimension_index],
                    candidate[dimension_index],
                )
            )

    aggregate_profile = np.mean(component_profiles, axis=1)
    return aggregate_profile, component_profiles


def _query_frame_range(
    frame_times_seconds: np.ndarray,
    start_seconds: float,
    end_seconds: float,
    *,
    duration_seconds: float,
) -> tuple[int, int]:
    if not np.isfinite(start_seconds) or not np.isfinite(end_seconds):
        raise ValueError("selected passage bounds must be finite")
    if start_seconds < 0:
        raise ValueError("selected passage starts before the source")
    if end_seconds <= start_seconds:
        raise ValueError("selected passage must have positive duration")
    if end_seconds > duration_seconds + _NUMERIC_ATOL:
        raise ValueError("selected passage ends after the source duration")

    selected = np.flatnonzero(
        np.logical_and(
            frame_times_seconds >= start_seconds,
            frame_times_seconds < end_seconds,
        )
    )
    if len(selected) < MIN_QUERY_FRAMES:
        raise ValueError(
            f"selected passage must contain at least {MIN_QUERY_FRAMES} evidence frames"
        )
    if selected[-1] - selected[0] + 1 != len(selected):
        raise ValueError("selected passage evidence frames must be contiguous")
    return int(selected[0]), int(selected[-1] + 1)


def _windows_overlap(start_a: int, start_b: int, window_frames: int) -> bool:
    return start_a < start_b + window_frames and start_a + window_frames > start_b


def find_similar_moments(
    report: PerceptualEvidenceReport,
    *,
    evidence_report_version_id: UUID,
    query_start_seconds: float,
    query_end_seconds: float,
    max_matches: int = DEFAULT_MAX_MATCHES,
) -> SimilarMomentsObservation:
    """Rank bounded non-overlapping same-Work windows for one selected passage.

    The method intentionally has no semantic abstention threshold yet. Historical
    #822 evidence did not establish a trustworthy cutoff, so weak queries still
    produce bounded experimental proposals when valid candidate windows exist.
    """

    if max_matches < 1 or max_matches > MAX_MATCHES:
        raise ValueError(f"max_matches must be between 1 and {MAX_MATCHES}")

    matrix = _build_fixed_perceptual_matrix(report)
    query_start_frame, query_end_frame = _query_frame_range(
        matrix.frame_times_seconds,
        query_start_seconds,
        query_end_seconds,
        duration_seconds=report.duration_seconds,
    )
    window_frames = query_end_frame - query_start_frame
    aggregate, components = _distance_profile(
        matrix,
        query_start_frame=query_start_frame,
        window_frames=window_frames,
    )

    query_duration = float(query_end_seconds - query_start_seconds)
    ranked: list[tuple[float, int]] = []
    for candidate_start, raw_distance in enumerate(aggregate):
        if _windows_overlap(candidate_start, query_start_frame, window_frames):
            continue
        candidate_time = float(matrix.frame_times_seconds[candidate_start])
        candidate_end = candidate_time + query_duration
        if candidate_end > report.duration_seconds + _NUMERIC_ATOL:
            continue
        ranked.append((float(raw_distance), candidate_start))
    ranked.sort(key=lambda item: (item[0], item[1]))

    selected: list[tuple[float, int]] = []
    for distance, candidate_start in ranked:
        if any(
            _windows_overlap(candidate_start, prior_start, window_frames)
            for _, prior_start in selected
        ):
            continue
        selected.append((distance, candidate_start))
        if len(selected) >= max_matches:
            break

    matches = [
        SimilarMomentMatch(
            start_seconds=float(matrix.frame_times_seconds[candidate_start]),
            end_seconds=float(matrix.frame_times_seconds[candidate_start]) + query_duration,
            distance=distance,
            component_distances={
                dimension: float(components[candidate_start, index])
                for index, dimension in enumerate(RECURRENCE_DIMENSIONS)
            },
        )
        for distance, candidate_start in selected
    ]

    return SimilarMomentsObservation(
        source_version_id=report.source_version_id,
        evidence_report_version_id=evidence_report_version_id,
        preprocessing_version=report.preprocessing_version,
        sample_rate=report.sample_rate,
        query_start_seconds=query_start_seconds,
        query_end_seconds=query_end_seconds,
        max_matches=max_matches,
        method=SimilarMomentsMethod(
            parameters={
                "constant_std_threshold": CONSTANT_STD_THRESHOLD,
                "minimum_query_frames": MIN_QUERY_FRAMES,
                "max_matches": max_matches,
            }
        ),
        matches=matches,
        no_match_reason=None if matches else "no_valid_non_overlapping_candidate_windows",
    )


__all__ = [
    "DEFAULT_MAX_MATCHES",
    "MAX_MATCHES",
    "RECURRENCE_DIMENSIONS",
    "SimilarMomentMatch",
    "SimilarMomentsMethod",
    "SimilarMomentsObservation",
    "find_similar_moments",
]

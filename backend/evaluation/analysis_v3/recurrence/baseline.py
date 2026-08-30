"""Equal-input NumPy control for selected-passage recurrence evaluation.

This module is evaluation-only. It deliberately consumes the already-promoted
perceptual evidence contract and defines the exact distance semantics that an
OSS candidate such as STUMPY must match in #812. It does not assign musical
section/motif identity and it is not a production similarity engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from uuid import UUID

import numpy as np

from domain.perceptual_report import PerceptualEvidenceReport

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
MIN_SUBJECT_FRAMES = 4


@dataclass(frozen=True)
class FixedPerceptualMatrix:
    """Six declared gain-independent perceptual dimensions on one frame grid."""

    source_version_id: UUID
    frame_times_seconds: np.ndarray
    values: np.ndarray  # shape: (6, n_frames)
    dimensions: tuple[str, ...] = RECURRENCE_DIMENSIONS


@dataclass(frozen=True)
class RecurrenceMatch:
    """Literal same-Work candidate under the declared descriptor representation."""

    start_seconds: float
    end_seconds: float
    distance: float
    component_distances: dict[str, float]


def _as_scalar_series(values: list[float] | list[list[float]], *, feature: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{feature} must be a scalar frame series")
    return array


def build_fixed_perceptual_matrix(report: PerceptualEvidenceReport) -> FixedPerceptualMatrix:
    """Build the fixed six-dimensional #812 recurrence representation.

    RMS is intentionally excluded. #455 promoted onset strength, centroid, and
    relative coarse-band energy as gain-independent within-Work evidence while
    RMS retains amplitude/codec semantics that should not be mixed into this
    first generic shape-recurrence distance.
    """

    required = {"onset_strength", "spectral_centroid", "relative_band_energy"}
    missing = required.difference(report.series)
    if missing:
        raise ValueError(f"missing required recurrence evidence: {sorted(missing)}")

    onset = report.series["onset_strength"]
    centroid = report.series["spectral_centroid"]
    bands = report.series["relative_band_energy"]
    selected = (onset, centroid, bands)

    for series in selected:
        if series.source_version_id != report.source_version_id:
            raise ValueError("perceptual recurrence evidence must share one source Version")
        if series.provenance.preprocessing_version != report.preprocessing_version:
            raise ValueError("perceptual recurrence evidence preprocessing must match the report")
        if series.channel_mode != "mono":
            raise ValueError("perceptual recurrence evidence must use the canonical mono contract")

    times = np.asarray(onset.frame_times_seconds, dtype=float)
    if times.ndim != 1 or len(times) < MIN_SUBJECT_FRAMES:
        raise ValueError("perceptual recurrence evidence has too few frames")
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("perceptual recurrence frame times must be finite and strictly increasing")

    for series in (centroid, bands):
        other_times = np.asarray(series.frame_times_seconds, dtype=float)
        if len(other_times) != len(times) or not np.allclose(
            other_times,
            times,
            rtol=0.0,
            atol=1e-9,
        ):
            raise ValueError("recurrence evidence dimensions must share one exact frame grid")

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
        raise ValueError("unexpected recurrence matrix shape")
    if not np.isfinite(values).all():
        raise ValueError("recurrence evidence must contain only finite values")

    return FixedPerceptualMatrix(
        source_version_id=report.source_version_id,
        frame_times_seconds=times,
        values=values,
    )


def _normalized_component_distance(query: np.ndarray, candidate: np.ndarray) -> float:
    """Length-normalized z-Euclidean distance with explicit constant semantics.

    This mirrors the STUMPY normalized-distance convention that two constant
    subsequences have distance 0 while exactly one constant subsequence has
    distance sqrt(m). Dividing all distances by sqrt(m) makes the returned
    component score comparable across allowed subject lengths.
    """

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
    matrix: FixedPerceptualMatrix,
    *,
    query_start_frame: int,
    window_frames: int,
) -> tuple[np.ndarray, np.ndarray]:
    if query_start_frame < 0 or window_frames < MIN_SUBJECT_FRAMES:
        raise ValueError("invalid recurrence query frame range")
    query_end = query_start_frame + window_frames
    if query_end > matrix.values.shape[1]:
        raise ValueError("recurrence query exceeds available evidence")

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


def _subject_frame_range(
    frame_times_seconds: np.ndarray,
    start_seconds: float,
    end_seconds: float,
) -> tuple[int, int]:
    if not np.isfinite(start_seconds) or not np.isfinite(end_seconds):
        raise ValueError("subject span bounds must be finite")
    if end_seconds <= start_seconds:
        raise ValueError("subject span end must be greater than start")

    selected = np.flatnonzero(
        np.logical_and(
            frame_times_seconds >= start_seconds,
            frame_times_seconds < end_seconds,
        )
    )
    if len(selected) < MIN_SUBJECT_FRAMES:
        raise ValueError(
            f"subject span must contain at least {MIN_SUBJECT_FRAMES} evidence frames"
        )
    if selected[-1] - selected[0] + 1 != len(selected):
        raise ValueError("subject evidence frames must be contiguous")
    return int(selected[0]), int(selected[-1] + 1)


def _windows_overlap(start_a: int, start_b: int, window_frames: int) -> bool:
    return start_a < start_b + window_frames and start_a + window_frames > start_b


def find_numpy_recurrence_matches(
    report: PerceptualEvidenceReport,
    subject_span_seconds: tuple[float, float],
    *,
    max_matches: int = 5,
    max_distance: float | None = None,
) -> list[RecurrenceMatch]:
    """Rank non-overlapping same-Work windows similar to one selected passage.

    Candidate similarity means only that the six declared descriptor trajectories
    have low normalized shape distance. It does not establish section, motif, or
    semantic identity. ``max_distance`` is evaluation policy, not confidence.
    """

    if max_matches <= 0:
        raise ValueError("max_matches must be positive")
    if max_distance is not None and (not np.isfinite(max_distance) or max_distance < 0):
        raise ValueError("max_distance must be finite and non-negative")

    matrix = build_fixed_perceptual_matrix(report)
    subject_start, subject_end = _subject_frame_range(
        matrix.frame_times_seconds,
        *subject_span_seconds,
    )
    window_frames = subject_end - subject_start
    aggregate, components = _distance_profile(
        matrix,
        query_start_frame=subject_start,
        window_frames=window_frames,
    )

    ranked: list[tuple[float, int]] = []
    for candidate_start, distance in enumerate(aggregate):
        if _windows_overlap(candidate_start, subject_start, window_frames):
            continue
        if max_distance is not None and distance > max_distance:
            continue
        ranked.append((float(distance), candidate_start))
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

    subject_duration = float(subject_span_seconds[1] - subject_span_seconds[0])
    matches: list[RecurrenceMatch] = []
    for distance, candidate_start in selected:
        candidate_time = float(matrix.frame_times_seconds[candidate_start])
        matches.append(
            RecurrenceMatch(
                start_seconds=candidate_time,
                end_seconds=candidate_time + subject_duration,
                distance=distance,
                component_distances={
                    dimension: float(components[candidate_start, index])
                    for index, dimension in enumerate(RECURRENCE_DIMENSIONS)
                },
            )
        )
    return matches

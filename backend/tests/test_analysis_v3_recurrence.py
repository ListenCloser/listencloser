from __future__ import annotations

from uuid import UUID

import numpy as np
import pytest

from backend.evaluation.analysis_v3.recurrence import (
    RECURRENCE_DIMENSIONS,
    build_fixed_perceptual_matrix,
    find_numpy_recurrence_matches,
)
from domain.perceptual_report import (
    PerceptualEvidenceReport,
    PerceptualProvenance,
    PerceptualSeriesEvidence,
)

FRAME_STEP_SECONDS = 0.1
SOURCE_VERSION_ID = UUID("00000000-0000-0000-0000-000000000812")


def _series(
    feature: str,
    values: np.ndarray,
    times: np.ndarray,
    *,
    unit: str,
    normalization: str,
    parameters: dict[str, object] | None = None,
) -> PerceptualSeriesEvidence:
    return PerceptualSeriesEvidence(
        feature=feature,
        frame_times_seconds=times.astype(float).tolist(),
        values=values.astype(float).tolist(),
        unit=unit,
        normalization=normalization,
        parameters=parameters or {},
        source_version_id=SOURCE_VERSION_ID,
        provenance=PerceptualProvenance(
            engine_version="test",
            parameters=parameters or {},
        ),
    )


def _report(matrix: np.ndarray) -> PerceptualEvidenceReport:
    assert matrix.ndim == 2 and matrix.shape[0] == 6
    times = np.arange(matrix.shape[1], dtype=float) * FRAME_STEP_SECONDS
    series = {
        "onset_strength": _series(
            "onset_strength",
            matrix[0],
            times,
            unit="librosa_onset_strength",
            normalization="librosa_default_log_power_mel_flux",
            parameters={"hop_length": 512},
        ),
        "spectral_centroid": _series(
            "spectral_centroid",
            matrix[1],
            times,
            unit="hz",
            normalization="none",
            parameters={"n_fft": 2048, "hop_length": 512},
        ),
        "relative_band_energy": _series(
            "relative_band_energy",
            matrix[2:].T,
            times,
            unit="fraction_of_frame_power",
            normalization="per_frame_total_stft_power",
            parameters={
                "n_fft": 2048,
                "hop_length": 512,
                "band_order": ["low", "low_mid", "mid", "high"],
            },
        ),
    }
    return PerceptualEvidenceReport(
        source_version_id=SOURCE_VERSION_ID,
        duration_seconds=float(matrix.shape[1] * FRAME_STEP_SECONDS),
        series=series,
    )


def _subject_span(start_frame: int, window_frames: int) -> tuple[float, float]:
    return (
        start_frame * FRAME_STEP_SECONDS,
        (start_frame + window_frames) * FRAME_STEP_SECONDS,
    )


def test_fixed_matrix_uses_six_declared_gain_independent_dimensions() -> None:
    matrix = np.arange(6 * 20, dtype=float).reshape(6, 20)
    recurrence = build_fixed_perceptual_matrix(_report(matrix))

    assert recurrence.dimensions == RECURRENCE_DIMENSIONS
    np.testing.assert_allclose(recurrence.values, matrix)
    assert "rms" not in recurrence.dimensions


def test_exact_repeated_window_is_top_non_overlapping_match() -> None:
    rng = np.random.default_rng(812)
    matrix = rng.normal(size=(6, 90))
    query = rng.normal(size=(6, 12))
    matrix[:, 10:22] = query
    matrix[:, 55:67] = query

    matches = find_numpy_recurrence_matches(
        _report(matrix),
        _subject_span(10, 12),
        max_matches=3,
    )

    assert matches[0].start_seconds == pytest.approx(5.5)
    assert matches[0].distance == pytest.approx(0.0, abs=1e-12)
    assert all(
        value == pytest.approx(0.0, abs=1e-12)
        for value in matches[0].component_distances.values()
    )
    assert all(
        not (match.start_seconds < 2.2 and match.end_seconds > 1.0)
        for match in matches
    )


def test_per_dimension_z_normalization_preserves_scaled_offset_shape() -> None:
    rng = np.random.default_rng(913)
    matrix = rng.normal(size=(6, 100))
    query = rng.normal(size=(6, 14))
    matrix[:, 8:22] = query

    scales = np.asarray([2.0, 0.5, 1.2, 0.8, 1.5, 0.7])[:, None]
    offsets = np.asarray([3.0, -2.0, 0.1, -0.4, 2.0, 1.0])[:, None]
    matrix[:, 65:79] = query * scales + offsets

    matches = find_numpy_recurrence_matches(
        _report(matrix),
        _subject_span(8, 14),
        max_matches=1,
    )

    assert matches[0].start_seconds == pytest.approx(6.5)
    assert matches[0].distance == pytest.approx(0.0, abs=1e-12)


def test_component_distances_keep_changed_dimension_diagnosable() -> None:
    rng = np.random.default_rng(1014)
    matrix = rng.normal(size=(6, 100))
    query = rng.normal(size=(6, 16))
    matrix[:, 10:26] = query
    changed = query.copy()
    changed[2] = np.roll(changed[2], 5)
    matrix[:, 60:76] = changed

    matches = find_numpy_recurrence_matches(
        _report(matrix),
        _subject_span(10, 16),
        max_matches=1,
    )

    assert matches[0].start_seconds == pytest.approx(6.0)
    assert matches[0].component_distances["band_low"] > 0.5
    for dimension in set(RECURRENCE_DIMENSIONS) - {"band_low"}:
        assert matches[0].component_distances[dimension] == pytest.approx(
            0.0,
            abs=1e-12,
        )


def test_constant_window_semantics_match_stumpy_normalized_convention() -> None:
    rng = np.random.default_rng(1115)
    matrix = rng.normal(size=(6, 80))
    query = np.asarray([[float(index)] * 10 for index in range(6)])
    matrix[:, 5:15] = query
    matrix[:, 45:55] = query

    matches = find_numpy_recurrence_matches(
        _report(matrix),
        _subject_span(5, 10),
        max_matches=1,
    )

    assert matches[0].start_seconds == pytest.approx(4.5)
    assert matches[0].distance == pytest.approx(0.0)


def test_explicit_distance_gate_can_return_no_match() -> None:
    rng = np.random.default_rng(1216)
    matrix = rng.normal(size=(6, 80))

    matches = find_numpy_recurrence_matches(
        _report(matrix),
        _subject_span(5, 12),
        max_matches=3,
        max_distance=0.01,
    )

    assert matches == []


def test_ranked_matches_are_non_overlapping_with_each_other() -> None:
    rng = np.random.default_rng(1317)
    matrix = rng.normal(size=(6, 100))
    query = rng.normal(size=(6, 10))
    matrix[:, 5:15] = query
    matrix[:, 50:60] = query
    matrix[:, 51:61] = query
    matrix[:, 80:90] = query

    matches = find_numpy_recurrence_matches(
        _report(matrix),
        _subject_span(5, 10),
        max_matches=3,
    )

    assert matches[0].start_seconds == pytest.approx(5.1)
    assert any(match.start_seconds == pytest.approx(8.0) for match in matches)
    for index, match in enumerate(matches):
        for other in matches[index + 1 :]:
            assert (
                match.end_seconds <= other.start_seconds
                or other.end_seconds <= match.start_seconds
            )


def test_mismatched_frame_grid_fails_closed() -> None:
    matrix = np.arange(6 * 30, dtype=float).reshape(6, 30)
    report = _report(matrix)
    shifted = report.series["spectral_centroid"].model_copy(
        update={
            "frame_times_seconds": [
                value + 0.01
                for value in report.series["spectral_centroid"].frame_times_seconds
            ]
        }
    )
    report = report.model_copy(
        update={"series": {**report.series, "spectral_centroid": shifted}}
    )

    with pytest.raises(ValueError, match="exact frame grid"):
        build_fixed_perceptual_matrix(report)

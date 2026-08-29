from __future__ import annotations

import numpy as np
import pytest
from backend.evaluation.analysis_v3.perceptual.comparisons import (
    compare_evidence_spans,
    compare_feature_spans,
)
from backend.evaluation.analysis_v3.perceptual.features import (
    extract_baseline_perceptual_evidence,
    rms_series,
)

SAMPLE_RATE = 22_050


def _sine(frequency_hz: float, duration_seconds: float, amplitude: float = 1.0) -> np.ndarray:
    times = np.arange(int(SAMPLE_RATE * duration_seconds), dtype=float) / SAMPLE_RATE
    return amplitude * np.sin(2.0 * np.pi * frequency_hz * times)


def test_span_comparison_reports_raw_rms_change_without_semantic_label() -> None:
    audio = np.concatenate([_sine(440.0, 1.0, 0.1), _sine(440.0, 1.0, 0.8)])
    comparison = compare_feature_spans(
        rms_series(audio, SAMPLE_RATE),
        (0.2, 0.8),
        (1.2, 1.8),
    )

    assert comparison["feature"] == "rms"
    assert comparison["aggregate_b"] / comparison["aggregate_a"] == pytest.approx(8.0, rel=0.03)
    assert comparison["delta_b_minus_a"] > 0
    assert "semantic_label" not in comparison


def test_span_comparison_keeps_feature_dimensions_separate() -> None:
    audio = np.concatenate([_sine(100.0, 1.0), _sine(6_000.0, 1.0)])
    evidence = extract_baseline_perceptual_evidence(audio, SAMPLE_RATE)
    comparisons = compare_evidence_spans(evidence, (0.2, 0.8), (1.2, 1.8))

    centroid_delta = comparisons["spectral_centroid"]["delta_b_minus_a"]
    band_delta = comparisons["relative_band_energy"]["delta_b_minus_a"]
    assert centroid_delta > 5_000
    assert band_delta[0] < -0.9
    assert band_delta[3] > 0.9


def test_span_comparison_rejects_invalid_or_empty_spans() -> None:
    series = rms_series(_sine(440.0, 1.0), SAMPLE_RATE)

    with pytest.raises(ValueError, match="greater than"):
        compare_feature_spans(series, (0.5, 0.5), (0.6, 0.8))
    with pytest.raises(ValueError, match="no feature frames"):
        compare_feature_spans(series, (2.0, 3.0), (0.2, 0.8))

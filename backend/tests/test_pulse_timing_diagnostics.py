"""Tests for pulse localization diagnostics used by claim-sufficiency gates."""

from __future__ import annotations

import pytest
from backend.evaluation.analysis_v3.pulse.metrics.beat import (
    EventTimingResult,
    compute_beat_f1,
    compute_event_timing,
)
from backend.evaluation.analysis_v3.pulse.run import _summarize_beat_evaluation
from backend.evaluation.analysis_v3.pulse.metrics.tempo import compute_tempo_error


def test_event_timing_reports_signed_error_and_match_coverage() -> None:
    result = compute_event_timing(
        [0.98, 2.03, 3.06, 10.0],
        [1.0, 2.0, 3.0],
        tolerance=0.07,
    )

    assert result.matched == 3
    assert result.reference_coverage == pytest.approx(1.0)
    assert result.predicted_coverage == pytest.approx(0.75)
    assert result.signed_errors_seconds == pytest.approx((-0.02, 0.03, 0.06))

    payload = result.to_dict()
    assert payload["signed_median_seconds"] == pytest.approx(0.03)
    assert payload["absolute_median_seconds"] == pytest.approx(0.03)
    assert payload["absolute_p95_seconds"] == pytest.approx(0.057)
    assert payload["absolute_max_seconds"] == pytest.approx(0.06)


def test_event_timing_with_no_matches_retains_denominators() -> None:
    result = compute_event_timing([10.0, 20.0], [1.0, 2.0], tolerance=0.07)

    assert result.matched == 0
    assert result.predicted == 2
    assert result.reference == 2
    assert result.to_dict()["absolute_median_seconds"] is None


def test_event_timing_rejects_negative_window() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        compute_event_timing([1.0], [1.0], tolerance=-0.01)


def test_f1_diagnostics_share_canonical_match_count_with_timing() -> None:
    predicted = [0.98, 2.03, 3.06, 10.0]
    reference = [1.0, 2.0, 3.0]

    f1 = compute_beat_f1(predicted, reference, tolerance=0.07)
    timing = compute_event_timing(predicted, reference, tolerance=0.07)

    assert f1.matched == timing.matched == 3
    assert f1.precision == pytest.approx(timing.predicted_coverage)
    assert f1.recall == pytest.approx(timing.reference_coverage)


def test_summary_aggregates_timing_errors_with_coverage_and_latency() -> None:
    timing_results = [
        EventTimingResult(
            tolerance_seconds=0.07,
            matched=2,
            predicted=3,
            reference=2,
            signed_errors_seconds=(-0.01, 0.02),
        ),
        EventTimingResult(
            tolerance_seconds=0.07,
            matched=1,
            predicted=2,
            reference=2,
            signed_errors_seconds=(0.04,),
        ),
    ]
    rows = [
        {"id": "one", "latency_seconds": 0.5},
        {"id": "two", "latency_seconds": 0.7},
    ]

    summary = _summarize_beat_evaluation(
        rows,
        beat_f1_values=[0.8, 0.5],
        downbeat_f1_values=[],
        tempo_results=[compute_tempo_error(120.0, 120.0)],
        beat_timing_results=timing_results,
    )

    timing = summary["beat_timing"]
    assert timing["matched"] == 3
    assert timing["reference"] == 4
    assert timing["predicted"] == 5
    assert timing["reference_coverage"] == pytest.approx(0.75)
    assert timing["predicted_coverage"] == pytest.approx(0.6)
    assert timing["absolute_error_seconds"]["median"] == pytest.approx(0.02)
    assert timing["absolute_p95_seconds"] == pytest.approx(0.038)
    assert summary["latency_seconds"]["mean"] == pytest.approx(0.6)

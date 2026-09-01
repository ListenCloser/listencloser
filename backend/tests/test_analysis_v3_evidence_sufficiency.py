from __future__ import annotations

import numpy as np
import pytest
from evaluation.analysis_v3.sufficiency.perturbations import (
    event_localization_summary,
    event_offsets_to_nearest_grid,
    metric_grid_shift_sensitivity,
    span_aggregate,
    span_boundary_sensitivity,
)


def test_event_offsets_preserve_signed_raw_timing_without_semantic_label() -> None:
    offsets, indices = event_offsets_to_nearest_grid(
        [0.98, 1.03, 2.0],
        [1.0, 2.0, 3.0],
    )

    np.testing.assert_allclose(offsets, [-0.02, 0.03, 0.0], atol=1e-12)
    np.testing.assert_array_equal(indices, [0, 0, 1])


def test_metric_grid_shift_reports_raw_offset_error() -> None:
    rows = metric_grid_shift_sensitivity(
        [0.98, 1.98, 2.98],
        [1.0, 2.0, 3.0],
        [0.02, -0.05],
    )

    assert rows[0]["mean_absolute_offset_error_seconds"] == pytest.approx(0.02)
    assert rows[0]["max_absolute_offset_error_seconds"] == pytest.approx(0.02)
    assert rows[0]["assignment_change_fraction"] == 0.0
    assert rows[1]["mean_absolute_offset_error_seconds"] == pytest.approx(0.05)


def test_metric_grid_shift_can_change_nearest_grid_assignment() -> None:
    row = metric_grid_shift_sensitivity(
        [1.49],
        [1.0, 2.0],
        [-0.1],
    )[0]

    assert row["assignment_change_fraction"] == 1.0


def test_localization_summary_keeps_coverage_separate_from_matched_event_error() -> None:
    complete = event_localization_summary(3, 3, [0.01, 0.01, 0.01])
    sparse = event_localization_summary(3, 1, [0.01])

    assert complete["median_absolute_error_seconds"] == pytest.approx(0.01)
    assert sparse["median_absolute_error_seconds"] == pytest.approx(0.01)
    assert complete["reference_coverage"] == 1.0
    assert sparse["reference_coverage"] == pytest.approx(1.0 / 3.0)
    assert sparse["unmatched_reference_count"] == 2


def test_localization_summary_handles_zero_matches_without_fabricating_error() -> None:
    summary = event_localization_summary(4, 0, [])

    assert summary["reference_coverage"] == 0.0
    assert summary["median_absolute_error_seconds"] is None
    assert summary["p95_absolute_error_seconds"] is None
    assert summary["max_absolute_error_seconds"] is None


def test_span_aggregate_is_seconds_authoritative() -> None:
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    values = [0.0, 0.0, 10.0, 10.0, 10.0]

    assert span_aggregate(times, values, 0.0, 3.0) == pytest.approx(10.0 / 3.0)
    assert span_aggregate(times, values, 0.0, 3.0, statistic="median") == 0.0


def test_boundary_shift_reports_aggregate_and_membership_change() -> None:
    rows = span_boundary_sensitivity(
        [0.0, 1.0, 2.0, 3.0, 4.0],
        [0.0, 0.0, 10.0, 10.0, 10.0],
        0.0,
        3.0,
        [(0.0, 1.0), (1.0, 0.0)],
    )

    assert rows[0]["reference_aggregate"] == pytest.approx(10.0 / 3.0)
    assert rows[0]["perturbed_aggregate"] == pytest.approx(5.0)
    assert rows[0]["aggregate_delta"] == pytest.approx(5.0 - 10.0 / 3.0)
    assert rows[0]["changed_membership_fraction"] == pytest.approx(0.2)

    assert rows[1]["perturbed_aggregate"] == pytest.approx(5.0)
    assert rows[1]["changed_membership_fraction"] == pytest.approx(0.2)


def test_perturbation_helpers_fail_closed_on_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        event_offsets_to_nearest_grid([1.0], [1.0, 1.0])
    with pytest.raises(ValueError, match="same length"):
        span_aggregate([0.0, 1.0], [1.0], 0.0, 1.0)
    with pytest.raises(ValueError, match="greater than"):
        span_boundary_sensitivity([0.0, 1.0], [1.0, 2.0], 1.0, 1.0, [(0.0, 0.0)])
    with pytest.raises(ValueError, match="length must equal"):
        event_localization_summary(3, 2, [0.01])
    with pytest.raises(ValueError, match="non-negative"):
        event_localization_summary(1, 1, [-0.01])

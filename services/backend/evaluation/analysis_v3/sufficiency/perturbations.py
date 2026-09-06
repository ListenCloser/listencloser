"""Theory-neutral perturbation helpers for claim-specific evidence sufficiency.

These utilities report raw downstream sensitivity to controlled upstream error.
They deliberately do not decide whether a musical claim such as "anticipates"
or "section contrast" is valid; the consuming claim owns that tolerance.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def _finite_1d(name: str, values: Sequence[float] | np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} must be a non-empty 1-D sequence")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _sorted_times(name: str, values: Sequence[float] | np.ndarray) -> np.ndarray:
    array = _finite_1d(name, values)
    if np.any(np.diff(array) <= 0):
        raise ValueError(f"{name} must be strictly increasing")
    return array


def event_offsets_to_nearest_grid(
    event_times_seconds: Sequence[float] | np.ndarray,
    grid_times_seconds: Sequence[float] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return signed event offsets and nearest grid-point indices.

    Offset is `event_time - nearest_grid_time`, so negative values occur before
    the nearest grid point and positive values occur after it. This measured
    sign is not itself a product-level anticipation/delay classification.
    """
    events = _finite_1d("event_times_seconds", event_times_seconds)
    grid = _sorted_times("grid_times_seconds", grid_times_seconds)

    insertion = np.searchsorted(grid, events, side="left")
    right = np.clip(insertion, 0, len(grid) - 1)
    left = np.clip(insertion - 1, 0, len(grid) - 1)
    left_distance = np.abs(events - grid[left])
    right_distance = np.abs(events - grid[right])
    nearest = np.where(left_distance <= right_distance, left, right)
    offsets = events - grid[nearest]
    return offsets, nearest.astype(int)


def metric_grid_shift_sensitivity(
    event_times_seconds: Sequence[float] | np.ndarray,
    reference_grid_seconds: Sequence[float] | np.ndarray,
    shifts_seconds: Sequence[float] | np.ndarray,
) -> list[dict[str, Any]]:
    """Measure how controlled whole-grid shifts alter event-relative timing."""
    events = _finite_1d("event_times_seconds", event_times_seconds)
    reference_grid = _sorted_times("reference_grid_seconds", reference_grid_seconds)
    shifts = _finite_1d("shifts_seconds", shifts_seconds)
    reference_offsets, reference_indices = event_offsets_to_nearest_grid(events, reference_grid)

    rows: list[dict[str, Any]] = []
    for shift in shifts:
        shifted_offsets, shifted_indices = event_offsets_to_nearest_grid(
            events,
            reference_grid + shift,
        )
        offset_error = shifted_offsets - reference_offsets
        rows.append(
            {
                "shift_seconds": float(shift),
                "mean_absolute_offset_error_seconds": float(np.mean(np.abs(offset_error))),
                "max_absolute_offset_error_seconds": float(np.max(np.abs(offset_error))),
                "assignment_change_fraction": float(np.mean(shifted_indices != reference_indices)),
                "reference_offsets_seconds": reference_offsets.astype(float).tolist(),
                "perturbed_offsets_seconds": shifted_offsets.astype(float).tolist(),
            }
        )
    return rows


def event_localization_summary(
    reference_event_count: int,
    matched_reference_count: int,
    absolute_errors_seconds: Sequence[float] | np.ndarray,
) -> dict[str, Any]:
    """Summarize event localization without hiding missed reference events.

    Timing error is conditional on matched events. Coverage therefore remains a
    first-class output: a detector that localizes a few matched events precisely
    must not look equivalent to one that localizes nearly every reference event.
    No musical acceptability threshold is applied here.
    """
    if isinstance(reference_event_count, bool) or not isinstance(reference_event_count, int):
        raise ValueError("reference_event_count must be an integer")
    if isinstance(matched_reference_count, bool) or not isinstance(matched_reference_count, int):
        raise ValueError("matched_reference_count must be an integer")
    if reference_event_count <= 0:
        raise ValueError("reference_event_count must be positive")
    if matched_reference_count < 0 or matched_reference_count > reference_event_count:
        raise ValueError("matched_reference_count must be between zero and reference_event_count")

    errors = np.asarray(absolute_errors_seconds, dtype=float)
    if errors.ndim != 1:
        raise ValueError("absolute_errors_seconds must be a 1-D sequence")
    if len(errors) != matched_reference_count:
        raise ValueError("absolute_errors_seconds length must equal matched_reference_count")
    if not np.isfinite(errors).all():
        raise ValueError("absolute_errors_seconds must contain only finite values")
    if np.any(errors < 0):
        raise ValueError("absolute_errors_seconds must be non-negative")

    summary: dict[str, Any] = {
        "reference_event_count": reference_event_count,
        "matched_reference_count": matched_reference_count,
        "unmatched_reference_count": reference_event_count - matched_reference_count,
        "reference_coverage": matched_reference_count / reference_event_count,
        "median_absolute_error_seconds": None,
        "p95_absolute_error_seconds": None,
        "max_absolute_error_seconds": None,
    }
    if matched_reference_count:
        summary.update(
            {
                "median_absolute_error_seconds": float(np.median(errors)),
                "p95_absolute_error_seconds": float(np.percentile(errors, 95)),
                "max_absolute_error_seconds": float(np.max(errors)),
            }
        )
    return summary


def _span_mask(times: np.ndarray, start_seconds: float, end_seconds: float) -> np.ndarray:
    if not np.isfinite(start_seconds) or not np.isfinite(end_seconds):
        raise ValueError("span bounds must be finite")
    if end_seconds <= start_seconds:
        raise ValueError("span end must be greater than span start")
    return np.logical_and(times >= start_seconds, times < end_seconds)


def span_aggregate(
    frame_times_seconds: Sequence[float] | np.ndarray,
    values: Sequence[float] | np.ndarray,
    start_seconds: float,
    end_seconds: float,
    *,
    statistic: str = "mean",
) -> float:
    """Aggregate a scalar time series over a half-open seconds span."""
    times = _sorted_times("frame_times_seconds", frame_times_seconds)
    series = _finite_1d("values", values)
    if len(times) != len(series):
        raise ValueError("frame_times_seconds and values must have the same length")

    mask = _span_mask(times, start_seconds, end_seconds)
    if not np.any(mask):
        raise ValueError("span contains no frames")
    selected = series[mask]
    if statistic == "mean":
        return float(np.mean(selected))
    if statistic == "median":
        return float(np.median(selected))
    raise ValueError("statistic must be 'mean' or 'median'")


def span_boundary_sensitivity(
    frame_times_seconds: Sequence[float] | np.ndarray,
    values: Sequence[float] | np.ndarray,
    reference_start_seconds: float,
    reference_end_seconds: float,
    perturbations_seconds: Sequence[tuple[float, float]],
    *,
    statistic: str = "mean",
) -> list[dict[str, Any]]:
    """Measure aggregate sensitivity to independent start/end boundary shifts."""
    times = _sorted_times("frame_times_seconds", frame_times_seconds)
    series = _finite_1d("values", values)
    if len(times) != len(series):
        raise ValueError("frame_times_seconds and values must have the same length")

    reference_mask = _span_mask(times, reference_start_seconds, reference_end_seconds)
    if not np.any(reference_mask):
        raise ValueError("reference span contains no frames")
    reference_value = span_aggregate(
        times,
        series,
        reference_start_seconds,
        reference_end_seconds,
        statistic=statistic,
    )

    rows: list[dict[str, Any]] = []
    for start_shift, end_shift in perturbations_seconds:
        perturbed_start = reference_start_seconds + float(start_shift)
        perturbed_end = reference_end_seconds + float(end_shift)
        perturbed_mask = _span_mask(times, perturbed_start, perturbed_end)
        if not np.any(perturbed_mask):
            raise ValueError("perturbed span contains no frames")
        perturbed_value = span_aggregate(
            times,
            series,
            perturbed_start,
            perturbed_end,
            statistic=statistic,
        )
        rows.append(
            {
                "start_shift_seconds": float(start_shift),
                "end_shift_seconds": float(end_shift),
                "reference_aggregate": reference_value,
                "perturbed_aggregate": perturbed_value,
                "aggregate_delta": perturbed_value - reference_value,
                "changed_membership_fraction": float(np.mean(reference_mask != perturbed_mask)),
            }
        )
    return rows

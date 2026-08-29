"""Evaluation-only A/B comparison helpers for measured perceptual evidence."""

from __future__ import annotations

from typing import Any

import numpy as np

from .features import FeatureSeries


def _span_values(
    series: FeatureSeries,
    start_seconds: float,
    end_seconds: float,
) -> np.ndarray:
    if not np.isfinite(start_seconds) or not np.isfinite(end_seconds):
        raise ValueError("span bounds must be finite")
    if end_seconds <= start_seconds:
        raise ValueError("span end must be greater than span start")

    times = np.asarray(series.frame_times_seconds, dtype=float)
    values = np.asarray(series.values, dtype=float)
    if len(times) != len(values):
        raise ValueError("feature times and values must have the same length")
    mask = np.logical_and(times >= start_seconds, times < end_seconds)
    if not np.any(mask):
        raise ValueError("span contains no feature frames")
    return values[mask]


def _aggregate(values: np.ndarray, statistic: str) -> np.ndarray:
    if statistic == "mean":
        return np.asarray(np.mean(values, axis=0), dtype=float)
    if statistic == "median":
        return np.asarray(np.median(values, axis=0), dtype=float)
    raise ValueError("statistic must be 'mean' or 'median'")


def _json_value(value: np.ndarray) -> float | list[float]:
    if value.ndim == 0:
        return float(value)
    return value.astype(float).tolist()


def compare_feature_spans(
    series: FeatureSeries,
    span_a_seconds: tuple[float, float],
    span_b_seconds: tuple[float, float],
    *,
    statistic: str = "median",
) -> dict[str, Any]:
    """Compare one measured feature across two explicit seconds spans.

    The result is a raw aggregate/delta in the feature's own units. It does not
    attach semantic wording such as brighter, fuller, exciting, or dramatic.
    """
    aggregate_a = _aggregate(_span_values(series, *span_a_seconds), statistic)
    aggregate_b = _aggregate(_span_values(series, *span_b_seconds), statistic)
    delta = aggregate_b - aggregate_a
    return {
        "feature": series.feature,
        "unit": series.unit,
        "normalization": series.normalization,
        "channel_mode": series.channel_mode,
        "statistic": statistic,
        "span_a_seconds": [float(span_a_seconds[0]), float(span_a_seconds[1])],
        "span_b_seconds": [float(span_b_seconds[0]), float(span_b_seconds[1])],
        "aggregate_a": _json_value(aggregate_a),
        "aggregate_b": _json_value(aggregate_b),
        "delta_b_minus_a": _json_value(delta),
    }


def compare_evidence_spans(
    evidence: dict[str, FeatureSeries],
    span_a_seconds: tuple[float, float],
    span_b_seconds: tuple[float, float],
    *,
    statistic: str = "median",
) -> dict[str, dict[str, Any]]:
    """Run the same explicit A/B comparison over each available evidence series."""
    return {
        name: compare_feature_spans(
            series,
            span_a_seconds,
            span_b_seconds,
            statistic=statistic,
        )
        for name, series in evidence.items()
    }

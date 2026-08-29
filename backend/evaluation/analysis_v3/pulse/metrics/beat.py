"""Beat and downbeat evaluation metrics using canonical mir_eval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mir_eval.beat
import mir_eval.util
import numpy as np


@dataclass(frozen=True)
class BeatF1Result:
    precision: float
    recall: float
    f1: float
    matched: int
    predicted: int
    reference: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "matched": self.matched,
            "predicted": self.predicted,
            "reference": self.reference,
        }


@dataclass(frozen=True)
class EventTimingResult:
    """One-to-one matched event timing errors under an explicit window."""

    tolerance_seconds: float
    matched: int
    predicted: int
    reference: int
    signed_errors_seconds: tuple[float, ...]

    @property
    def reference_coverage(self) -> float:
        return self.matched / self.reference if self.reference else 0.0

    @property
    def predicted_coverage(self) -> float:
        return self.matched / self.predicted if self.predicted else 0.0

    def to_dict(self) -> dict[str, Any]:
        errors = np.asarray(self.signed_errors_seconds, dtype=float)
        absolute = np.abs(errors)
        if errors.size == 0:
            return {
                "tolerance_seconds": self.tolerance_seconds,
                "matched": self.matched,
                "predicted": self.predicted,
                "reference": self.reference,
                "reference_coverage": round(self.reference_coverage, 4),
                "predicted_coverage": round(self.predicted_coverage, 4),
                "signed_mean_seconds": None,
                "signed_median_seconds": None,
                "absolute_mean_seconds": None,
                "absolute_median_seconds": None,
                "absolute_p95_seconds": None,
                "absolute_max_seconds": None,
            }

        return {
            "tolerance_seconds": self.tolerance_seconds,
            "matched": self.matched,
            "predicted": self.predicted,
            "reference": self.reference,
            "reference_coverage": round(self.reference_coverage, 4),
            "predicted_coverage": round(self.predicted_coverage, 4),
            "signed_mean_seconds": round(float(np.mean(errors)), 6),
            "signed_median_seconds": round(float(np.median(errors)), 6),
            "absolute_mean_seconds": round(float(np.mean(absolute)), 6),
            "absolute_median_seconds": round(float(np.median(absolute)), 6),
            "absolute_p95_seconds": round(float(np.percentile(absolute, 95)), 6),
            "absolute_max_seconds": round(float(np.max(absolute)), 6),
        }


def match_timestamps(
    predicted: list[float],
    reference: list[float],
    tolerance: float = 0.07,
) -> tuple[int, list[float], list[float]]:
    """Greedy timestamp matching for debugging/diagnostics.

    Returns (matched_count, unmatched_pred, unmatched_ref).
    """
    pred = sorted(predicted)
    ref = sorted(reference)
    matched = 0
    unmatched_pred = list(pred)
    unmatched_ref = list(ref)

    for r in ref:
        for i, p in enumerate(unmatched_pred):
            if abs(p - r) <= tolerance:
                matched += 1
                unmatched_pred.pop(i)
                unmatched_ref.remove(r)
                break

    return matched, unmatched_pred, unmatched_ref


def compute_event_timing(
    predicted: list[float],
    reference: list[float],
    tolerance: float = 0.07,
) -> EventTimingResult:
    """Measure localization error for canonical one-to-one event matches.

    Matching uses ``mir_eval.util.match_events`` with the same window used by
    beat/downbeat F-measure. Signed error is ``predicted - reference``.
    Coverage is retained because timing statistics over matched events alone
    would be misleading for a tracker that misses or mis-phases most events.
    """
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    pred_arr = np.asarray(sorted(predicted), dtype=float)
    ref_arr = np.asarray(sorted(reference), dtype=float)
    if pred_arr.size == 0 or ref_arr.size == 0:
        return EventTimingResult(
            tolerance_seconds=tolerance,
            matched=0,
            predicted=len(predicted),
            reference=len(reference),
            signed_errors_seconds=(),
        )

    matching = mir_eval.util.match_events(ref_arr, pred_arr, tolerance)
    errors = tuple(float(pred_arr[pred_index] - ref_arr[ref_index]) for ref_index, pred_index in matching)
    return EventTimingResult(
        tolerance_seconds=tolerance,
        matched=len(matching),
        predicted=len(predicted),
        reference=len(reference),
        signed_errors_seconds=errors,
    )


def compute_beat_f1(
    predicted: list[float],
    reference: list[float],
    tolerance: float = 0.07,
) -> BeatF1Result:
    """Compute beat F-measure using canonical mir_eval.beat.f_measure.

    Uses the standard MIREX convention with 70ms tolerance.
    """
    if not reference:
        return BeatF1Result(
            precision=0.0,
            recall=0.0,
            f1=0.0,
            matched=0,
            predicted=len(predicted),
            reference=0,
        )
    if not predicted:
        return BeatF1Result(
            precision=0.0,
            recall=0.0,
            f1=0.0,
            matched=0,
            predicted=0,
            reference=len(reference),
        )

    pred_arr = np.array(sorted(predicted))
    ref_arr = np.array(sorted(reference))

    try:
        f1 = mir_eval.beat.f_measure(ref_arr, pred_arr, f_measure_threshold=tolerance)
    except Exception:
        f1 = 0.0

    matched, _, _ = match_timestamps(predicted, reference, tolerance)
    p = matched / len(predicted) if predicted else 0.0
    r = matched / len(reference) if reference else 0.0

    return BeatF1Result(
        precision=p,
        recall=r,
        f1=f1,
        matched=matched,
        predicted=len(predicted),
        reference=len(reference),
    )


def compute_downbeat_f1(
    predicted: list[float],
    reference: list[float],
    tolerance: float = 0.07,
) -> BeatF1Result:
    """Compute downbeat F-measure using canonical mir_eval.beat.f_measure."""
    return compute_beat_f1(predicted, reference, tolerance)

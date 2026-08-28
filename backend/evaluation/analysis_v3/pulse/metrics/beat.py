"""Beat and downbeat evaluation metrics using canonical mir_eval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mir_eval.beat
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

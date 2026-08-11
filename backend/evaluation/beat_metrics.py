"""Beat and downbeat evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BeatMetrics:
    bpm_absolute_error: float | None
    bpm_relative_error_pct: float | None
    beat_precision: float | None
    beat_recall: float | None
    beat_f1: float | None
    downbeat_precision: float | None
    downbeat_recall: float | None
    downbeat_f1: float | None
    reference_beat_count: int
    predicted_beat_count: int
    matched_beat_count: int
    matched_downbeat_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "bpm_absolute_error": (
                round(self.bpm_absolute_error, 3) if self.bpm_absolute_error is not None else None
            ),
            "bpm_relative_error_pct": (
                round(self.bpm_relative_error_pct, 2)
                if self.bpm_relative_error_pct is not None
                else None
            ),
            "beat_precision": (
                round(self.beat_precision, 4) if self.beat_precision is not None else None
            ),
            "beat_recall": (round(self.beat_recall, 4) if self.beat_recall is not None else None),
            "beat_f1": (round(self.beat_f1, 4) if self.beat_f1 is not None else None),
            "downbeat_precision": (
                round(self.downbeat_precision, 4) if self.downbeat_precision is not None else None
            ),
            "downbeat_recall": (
                round(self.downbeat_recall, 4) if self.downbeat_recall is not None else None
            ),
            "downbeat_f1": (round(self.downbeat_f1, 4) if self.downbeat_f1 is not None else None),
            "reference_beat_count": self.reference_beat_count,
            "predicted_beat_count": self.predicted_beat_count,
            "matched_beat_count": self.matched_beat_count,
            "matched_downbeat_count": self.matched_downbeat_count,
        }


def _match_timestamps(
    predicted: list[float],
    reference: list[float],
    tolerance: float,
) -> tuple[int, list[float], list[float]]:
    """Greedy timestamp matching. Returns (matched_count, unmatched_pred, unmatched_ref)."""
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
                break

    return matched, unmatched_pred, unmatched_ref


def compute_beat_metrics(
    predicted_beats: list[float] | None,
    predicted_bpm: float | None,
    predicted_downbeats: list[float] | None,
    reference_beats: list[float] | None,
    reference_bpm: float | None,
    reference_downbeats: list[float] | None,
    tolerance: float = 0.07,
) -> BeatMetrics:
    bpm_abs = None
    bpm_rel_pct = None
    beat_p = beat_r = beat_f1 = None
    db_p = db_r = db_f1 = None
    matched_beats = 0
    matched_dbs = 0

    if reference_bpm is not None and predicted_bpm is not None:
        bpm_abs = abs(predicted_bpm - reference_bpm)
        bpm_rel_pct = bpm_abs / reference_bpm * 100 if reference_bpm > 0 else 0.0

    if reference_beats is not None and predicted_beats is not None:
        matched_beats, _, _ = _match_timestamps(predicted_beats, reference_beats, tolerance)
        p_count = len(predicted_beats)
        r_count = len(reference_beats)
        beat_p = matched_beats / p_count if p_count > 0 else 0.0
        beat_r = matched_beats / r_count if r_count > 0 else 0.0
        beat_f1 = 2 * beat_p * beat_r / (beat_p + beat_r) if (beat_p + beat_r) > 0 else 0.0

    if reference_downbeats is not None and predicted_downbeats is not None:
        matched_dbs, _, _ = _match_timestamps(
            predicted_downbeats, reference_downbeats, tolerance * 2
        )
        p_db = len(predicted_downbeats)
        r_db = len(reference_downbeats)
        db_p = matched_dbs / p_db if p_db > 0 else 0.0
        db_r = matched_dbs / r_db if r_db > 0 else 0.0
        db_f1 = 2 * db_p * db_r / (db_p + db_r) if (db_p + db_r) > 0 else 0.0

    return BeatMetrics(
        bpm_absolute_error=bpm_abs,
        bpm_relative_error_pct=bpm_rel_pct,
        beat_precision=beat_p,
        beat_recall=beat_r,
        beat_f1=beat_f1,
        downbeat_precision=db_p,
        downbeat_recall=db_r,
        downbeat_f1=db_f1,
        reference_beat_count=len(reference_beats) if reference_beats else 0,
        predicted_beat_count=len(predicted_beats) if predicted_beats else 0,
        matched_beat_count=matched_beats,
        matched_downbeat_count=matched_dbs,
    )

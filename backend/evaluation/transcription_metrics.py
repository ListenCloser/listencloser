"""Note-level transcription evaluation metrics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Note:
    pitch: int
    start: float
    end: float
    velocity: int = 64

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Note:
        return cls(
            pitch=int(d["pitch"]),
            start=float(d["start"]),
            end=float(d["end"]),
            velocity=int(d.get("velocity", 64)),
        )


@dataclass(frozen=True)
class TranscriptionMetrics:
    onset_note_precision: float
    onset_note_recall: float
    onset_note_f1: float
    onset_offset_note_precision: float
    onset_offset_note_recall: float
    onset_offset_note_f1: float
    predicted_count: int
    reference_count: int
    onset_matched_count: int
    onset_offset_matched_count: int
    excessive_count: int
    missed_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "onset_note_precision": round(self.onset_note_precision, 4),
            "onset_note_recall": round(self.onset_note_recall, 4),
            "onset_note_f1": round(self.onset_note_f1, 4),
            "onset_offset_note_precision": round(self.onset_offset_note_precision, 4),
            "onset_offset_note_recall": round(self.onset_offset_note_recall, 4),
            "onset_offset_note_f1": round(self.onset_offset_note_f1, 4),
            "predicted_count": self.predicted_count,
            "reference_count": self.reference_count,
            "onset_matched_count": self.onset_matched_count,
            "onset_offset_matched_count": self.onset_offset_matched_count,
            "excessive_count": self.excessive_count,
            "missed_count": self.missed_count,
        }


def match_notes(
    predicted: Sequence[Note],
    reference: Sequence[Note],
    onset_tolerance: float = 0.05,
    offset_tolerance: float = 0.05,
) -> tuple[list[tuple[Note, Note]], list[Note], list[Note]]:
    """Greedy note matching by pitch + onset.

    Returns (matched_pairs, unmatched_predicted, unmatched_reference).
    """
    ref_remaining = list(reference)
    pred_remaining = list(predicted)
    matched: list[tuple[Note, Note]] = []

    pred_remaining.sort(key=lambda n: n.start)
    ref_remaining.sort(key=lambda n: n.start)

    for pred in list(pred_remaining):
        best_idx: int | None = None
        best_diff = float("inf")
        for i, ref in enumerate(ref_remaining):
            onset_diff = abs(pred.start - ref.start)
            if onset_diff <= onset_tolerance and pred.pitch == ref.pitch and onset_diff < best_diff:
                best_diff = onset_diff
                best_idx = i
        if best_idx is not None:
            matched.append((pred, ref_remaining[best_idx]))
            pred_remaining.remove(pred)
            ref_remaining.pop(best_idx)

    return matched, pred_remaining, ref_remaining


def compute_note_metrics(
    predicted: Sequence[Note],
    reference: Sequence[Note],
    onset_tolerance: float = 0.05,
    offset_tolerance: float = 0.05,
) -> TranscriptionMetrics:
    matched, excessive, missed = match_notes(predicted, reference, onset_tolerance)
    onset_matched = len(matched)
    pred_count = len(predicted)
    ref_count = len(reference)

    onset_precision = onset_matched / pred_count if pred_count > 0 else 0.0
    onset_recall = onset_matched / ref_count if ref_count > 0 else 0.0
    onset_f1 = (
        2 * onset_precision * onset_recall / (onset_precision + onset_recall)
        if (onset_precision + onset_recall) > 0
        else 0.0
    )

    offset_matched = sum(
        1
        for pred, ref in matched
        if math.isclose(pred.end, ref.end, abs_tol=offset_tolerance + 1e-12)
    )
    offset_precision = offset_matched / pred_count if pred_count > 0 else 0.0
    offset_recall = offset_matched / ref_count if ref_count > 0 else 0.0
    offset_f1 = (
        2 * offset_precision * offset_recall / (offset_precision + offset_recall)
        if (offset_precision + offset_recall) > 0
        else 0.0
    )

    return TranscriptionMetrics(
        onset_note_precision=onset_precision,
        onset_note_recall=onset_recall,
        onset_note_f1=onset_f1,
        onset_offset_note_precision=offset_precision,
        onset_offset_note_recall=offset_recall,
        onset_offset_note_f1=offset_f1,
        predicted_count=pred_count,
        reference_count=ref_count,
        onset_matched_count=onset_matched,
        onset_offset_matched_count=offset_matched,
        excessive_count=len(excessive),
        missed_count=len(missed),
    )

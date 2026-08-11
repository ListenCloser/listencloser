"""Note-level transcription evaluation metrics."""

from __future__ import annotations

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
    note_precision: float
    note_recall: float
    note_f1: float
    onset_precision: float
    onset_recall: float
    onset_f1: float
    predicted_count: int
    reference_count: int
    matched_count: int
    excessive_count: int
    missed_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_precision": round(self.note_precision, 4),
            "note_recall": round(self.note_recall, 4),
            "note_f1": round(self.note_f1, 4),
            "onset_precision": round(self.onset_precision, 4),
            "onset_recall": round(self.onset_recall, 4),
            "onset_f1": round(self.onset_f1, 4),
            "predicted_count": self.predicted_count,
            "reference_count": self.reference_count,
            "matched_count": self.matched_count,
            "excessive_count": self.excessive_count,
            "missed_count": self.missed_count,
        }


def match_notes(
    predicted: Sequence[Note],
    reference: Sequence[Note],
    onset_tolerance: float = 0.05,
) -> tuple[list[tuple[Note, Note]], list[Note], list[Note]]:
    """Greedy note matching.

    Returns (matched_pairs, unmatched_predicted, unmatched_reference).
    """
    ref_remaining = list(reference)
    pred_remaining = list(predicted)
    matched: list[tuple[Note, Note]] = []

    # Sort by start time for deterministic matching
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
) -> TranscriptionMetrics:
    matched, excessive, missed = match_notes(predicted, reference, onset_tolerance)
    matched_count = len(matched)
    pred_count = len(predicted)
    ref_count = len(reference)

    note_precision = matched_count / pred_count if pred_count > 0 else 0.0
    note_recall = matched_count / ref_count if ref_count > 0 else 0.0
    note_f1 = (
        2 * note_precision * note_recall / (note_precision + note_recall)
        if (note_precision + note_recall) > 0
        else 0.0
    )

    onset_matched = sum(1 for p, r in matched if abs(p.start - r.start) <= onset_tolerance)
    onset_precision = onset_matched / pred_count if pred_count > 0 else 0.0
    onset_recall = onset_matched / ref_count if ref_count > 0 else 0.0
    onset_f1 = (
        2 * onset_precision * onset_recall / (onset_precision + onset_recall)
        if (onset_precision + onset_recall) > 0
        else 0.0
    )

    return TranscriptionMetrics(
        note_precision=note_precision,
        note_recall=note_recall,
        note_f1=note_f1,
        onset_precision=onset_precision,
        onset_recall=onset_recall,
        onset_f1=onset_f1,
        predicted_count=pred_count,
        reference_count=ref_count,
        matched_count=matched_count,
        excessive_count=len(excessive),
        missed_count=len(missed),
    )

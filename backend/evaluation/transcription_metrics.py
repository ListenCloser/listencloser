"""Note-level transcription evaluation metrics.

Two matching criteria are reported separately:

- **onset-only**: a predicted note matches a reference note if their pitches
  agree and their onsets are within ``onset_tolerance`` seconds.
- **onset+offset**: additionally requires the note *offsets* (ends) to agree
  within ``offset_tolerance`` seconds.

``note_f1`` refers to the stricter onset+offset match; ``onset_f1`` refers to
the looser onset-only match. They are intentionally different so timing/duration
quality can be measured independently of onset detection.
"""

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
    # onset+offset (strict note) matching
    note_precision: float
    note_recall: float
    note_f1: float
    # onset-only matching
    onset_precision: float
    onset_recall: float
    onset_f1: float
    predicted_count: int
    reference_count: int
    matched_count: int  # onset+offset matched pairs
    onset_matched_count: int  # onset-only matched pairs
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
            "onset_matched_count": self.onset_matched_count,
            "excessive_count": self.excessive_count,
            "missed_count": self.missed_count,
        }


def match_notes(
    predicted: Sequence[Note],
    reference: Sequence[Note],
    onset_tolerance: float = 0.05,
) -> tuple[list[tuple[Note, Note]], list[Note], list[Note]]:
    """Greedy onset-only note matching by pitch + onset.

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
    onset_matched, excessive, missed = match_notes(predicted, reference, onset_tolerance)
    onset_matched_count = len(onset_matched)
    pred_count = len(predicted)
    ref_count = len(reference)

    # onset+offset: subset of onset-matched pairs whose offsets also agree.
    offset_matched = [
        (p, r)
        for p, r in onset_matched
        if math.isclose(p.end, r.end, abs_tol=offset_tolerance + 1e-12)
    ]
    matched_count = len(offset_matched)

    def _p_r_f1(matched: int, pred_n: int, ref_n: int) -> tuple[float, float, float]:
        p = matched / pred_n if pred_n > 0 else 0.0
        r = matched / ref_n if ref_n > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return p, r, f1

    note_p, note_r, note_f1 = _p_r_f1(matched_count, pred_count, ref_count)
    onset_p, onset_r, onset_f1 = _p_r_f1(onset_matched_count, pred_count, ref_count)

    return TranscriptionMetrics(
        note_precision=note_p,
        note_recall=note_r,
        note_f1=note_f1,
        onset_precision=onset_p,
        onset_recall=onset_r,
        onset_f1=onset_f1,
        predicted_count=pred_count,
        reference_count=ref_count,
        matched_count=matched_count,
        onset_matched_count=onset_matched_count,
        excessive_count=len(excessive),
        missed_count=len(missed),
    )

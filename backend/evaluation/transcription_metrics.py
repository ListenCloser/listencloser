"""Canonical note-level transcription evaluation metrics.

Matching and precision/recall/F1 are delegated to ``mir_eval.transcription``.
The repository keeps only a small adapter around its existing ``Note`` and
``TranscriptionMetrics`` result contracts.

Two criteria are reported separately:

- ``onset_*``: pitch + onset matching with offsets ignored;
- ``note_*``: pitch + onset + offset matching using mir_eval's standard
  duration-relative offset rule (20% of reference duration, with a 50 ms
  minimum by default).

The historical field names are preserved for durable result compatibility.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import mir_eval
import numpy as np


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
    # onset+pitch matching, ignoring offsets
    onset_precision: float
    onset_recall: float
    onset_f1: float
    predicted_count: int
    reference_count: int
    matched_count: int  # onset+offset matched pairs
    onset_matched_count: int  # onset+pitch matched pairs
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


def _mir_eval_inputs(notes: Sequence[Note]) -> tuple[np.ndarray, np.ndarray]:
    """Convert repository note events into mir_eval intervals and Hz pitches."""
    intervals = np.asarray([(note.start, note.end) for note in notes], dtype=float)
    if intervals.size == 0:
        intervals = np.empty((0, 2), dtype=float)
    else:
        intervals = intervals.reshape((-1, 2))
    midi_pitches = np.asarray([note.pitch for note in notes], dtype=float)
    return intervals, np.asarray(mir_eval.util.midi_to_hz(midi_pitches), dtype=float)


def match_notes(
    predicted: Sequence[Note],
    reference: Sequence[Note],
    onset_tolerance: float = 0.05,
) -> tuple[list[tuple[Note, Note]], list[Note], list[Note]]:
    """Return canonical maximum pitch+onset matches and unmatched notes.

    This preserves the historical helper contract while replacing the local
    greedy matcher with mir_eval's maximum bipartite matching. Offsets are
    intentionally ignored here; strict offset-aware scoring is computed by
    ``compute_note_metrics``.
    """
    predicted_notes = list(predicted)
    reference_notes = list(reference)
    ref_intervals, ref_pitches = _mir_eval_inputs(reference_notes)
    pred_intervals, pred_pitches = _mir_eval_inputs(predicted_notes)

    matching = mir_eval.transcription.match_notes(
        ref_intervals,
        ref_pitches,
        pred_intervals,
        pred_pitches,
        onset_tolerance=onset_tolerance,
        offset_ratio=None,
    )
    matched_ref = {ref_index for ref_index, _ in matching}
    matched_pred = {pred_index for _, pred_index in matching}
    matched_pairs = [
        (predicted_notes[pred_index], reference_notes[ref_index])
        for ref_index, pred_index in matching
    ]
    unmatched_predicted = [
        note for index, note in enumerate(predicted_notes) if index not in matched_pred
    ]
    unmatched_reference = [
        note for index, note in enumerate(reference_notes) if index not in matched_ref
    ]
    return matched_pairs, unmatched_predicted, unmatched_reference


def compute_note_metrics(
    predicted: Sequence[Note],
    reference: Sequence[Note],
    onset_tolerance: float = 0.05,
    offset_tolerance: float = 0.05,
) -> TranscriptionMetrics:
    """Score note transcription with mir_eval's canonical matching rules.

    ``offset_tolerance`` is retained for API compatibility and is passed as
    mir_eval's minimum offset tolerance. The canonical duration-relative
    ``offset_ratio=0.2`` remains enabled, so long reference notes receive the
    standard 20% offset window rather than a repository-specific fixed window.
    """
    predicted_notes = list(predicted)
    reference_notes = list(reference)
    pred_count = len(predicted_notes)
    ref_count = len(reference_notes)

    ref_intervals, ref_pitches = _mir_eval_inputs(reference_notes)
    pred_intervals, pred_pitches = _mir_eval_inputs(predicted_notes)

    note_precision, note_recall, note_f1, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_intervals,
        ref_pitches,
        pred_intervals,
        pred_pitches,
        onset_tolerance=onset_tolerance,
        offset_ratio=0.2,
        offset_min_tolerance=offset_tolerance,
    )
    onset_precision, onset_recall, onset_f1, _ = (
        mir_eval.transcription.precision_recall_f1_overlap(
            ref_intervals,
            ref_pitches,
            pred_intervals,
            pred_pitches,
            onset_tolerance=onset_tolerance,
            offset_ratio=None,
        )
    )

    strict_matching = mir_eval.transcription.match_notes(
        ref_intervals,
        ref_pitches,
        pred_intervals,
        pred_pitches,
        onset_tolerance=onset_tolerance,
        offset_ratio=0.2,
        offset_min_tolerance=offset_tolerance,
    )
    onset_matching = mir_eval.transcription.match_notes(
        ref_intervals,
        ref_pitches,
        pred_intervals,
        pred_pitches,
        onset_tolerance=onset_tolerance,
        offset_ratio=None,
    )
    matched_count = len(strict_matching)
    onset_matched_count = len(onset_matching)

    return TranscriptionMetrics(
        note_precision=float(note_precision),
        note_recall=float(note_recall),
        note_f1=float(note_f1),
        onset_precision=float(onset_precision),
        onset_recall=float(onset_recall),
        onset_f1=float(onset_f1),
        predicted_count=pred_count,
        reference_count=ref_count,
        matched_count=matched_count,
        onset_matched_count=onset_matched_count,
        excessive_count=pred_count - onset_matched_count,
        missed_count=ref_count - onset_matched_count,
    )

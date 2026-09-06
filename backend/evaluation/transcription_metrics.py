"""Canonical note-level transcription metrics backed by ``mir_eval``.

The historical result fields stay stable, but matching and scoring belong to
``mir_eval.transcription`` rather than repository-owned metric code.
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
    note_precision: float
    note_recall: float
    note_f1: float
    onset_precision: float
    onset_recall: float
    onset_f1: float
    predicted_count: int
    reference_count: int
    matched_count: int
    onset_matched_count: int
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


def _mir_eval_inputs(notes: Sequence[Note]) -> tuple[list[Note], np.ndarray, np.ndarray]:
    items = list(notes)
    intervals = np.asarray([(note.start, note.end) for note in items], dtype=float).reshape((-1, 2))
    midi = np.asarray([note.pitch for note in items], dtype=float)
    pitches_hz = np.asarray(mir_eval.util.midi_to_hz(midi), dtype=float)
    return items, intervals, pitches_hz


def match_notes(
    predicted: Sequence[Note],
    reference: Sequence[Note],
    onset_tolerance: float = 0.05,
) -> tuple[list[tuple[Note, Note]], list[Note], list[Note]]:
    """Preserve the old helper contract using mir_eval maximum matching."""
    pred, pred_intervals, pred_pitches = _mir_eval_inputs(predicted)
    ref, ref_intervals, ref_pitches = _mir_eval_inputs(reference)
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
    return (
        [(pred[pred_index], ref[ref_index]) for ref_index, pred_index in matching],
        [note for index, note in enumerate(pred) if index not in matched_pred],
        [note for index, note in enumerate(ref) if index not in matched_ref],
    )


def compute_note_metrics(
    predicted: Sequence[Note],
    reference: Sequence[Note],
    onset_tolerance: float = 0.05,
    offset_tolerance: float = 0.05,
) -> TranscriptionMetrics:
    """Score with mir_eval's standard pitch/onset/offset transcription rules.

    ``offset_tolerance`` remains for caller compatibility and becomes mir_eval's
    minimum offset tolerance. The standard 20% reference-duration tolerance is
    retained instead of the former repository-specific fixed offset window.
    """
    pred, pred_intervals, pred_pitches = _mir_eval_inputs(predicted)
    ref, ref_intervals, ref_pitches = _mir_eval_inputs(reference)
    kwargs = {
        "onset_tolerance": onset_tolerance,
        "offset_ratio": 0.2,
        "offset_min_tolerance": offset_tolerance,
    }
    scores = mir_eval.transcription.evaluate(
        ref_intervals,
        ref_pitches,
        pred_intervals,
        pred_pitches,
        **kwargs,
    )
    strict_matching = mir_eval.transcription.match_notes(
        ref_intervals,
        ref_pitches,
        pred_intervals,
        pred_pitches,
        **kwargs,
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
        note_precision=float(scores["Precision"]),
        note_recall=float(scores["Recall"]),
        note_f1=float(scores["F-measure"]),
        onset_precision=float(scores["Precision_no_offset"]),
        onset_recall=float(scores["Recall_no_offset"]),
        onset_f1=float(scores["F-measure_no_offset"]),
        predicted_count=len(pred),
        reference_count=len(ref),
        matched_count=matched_count,
        onset_matched_count=onset_matched_count,
        excessive_count=len(pred) - onset_matched_count,
        missed_count=len(ref) - onset_matched_count,
    )

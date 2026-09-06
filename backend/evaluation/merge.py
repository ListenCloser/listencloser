"""Evaluation-only note merging for stem-wise transcription.

Concatenating per-stem predictions can produce near-duplicate notes (the same
musical event predicted from two stems). This module de-duplicates
conservatively: two predicted notes are considered the same event when their
pitches match and their onsets are within ``onset_tolerance`` AND their
durations overlap substantially.
"""

from __future__ import annotations

from evaluation.transcription_metrics import Note


def merge_notes(
    stem_predictions: list[list[Note]],
    onset_tolerance: float = 0.05,
    overlap_ratio: float = 0.5,
) -> list[Note]:
    """Merge note lists from multiple stems, de-duplicating near-identical notes.

    Returns a single sorted note list.
    """
    notes: list[Note] = []
    for stem_notes in stem_predictions:
        notes.extend(stem_notes)
    notes.sort(key=lambda n: (n.start, n.pitch, n.end))

    merged: list[Note] = []
    for note in notes:
        duplicate_idx: int | None = None
        for i, kept in enumerate(merged):
            if kept.pitch != note.pitch:
                continue
            if abs(kept.start - note.start) > onset_tolerance:
                continue
            overlap = min(kept.end, note.end) - max(kept.start, note.start)
            shorter = min(kept.end - kept.start, note.end - note.start)
            if shorter <= 0:
                continue
            if overlap / shorter >= overlap_ratio:
                duplicate_idx = i
                break
        if duplicate_idx is None:
            merged.append(note)
        else:
            # Keep the longer note when a duplicate is found.
            kept = merged[duplicate_idx]
            if note.end - note.start > kept.end - kept.start:
                merged[duplicate_idx] = note

    merged.sort(key=lambda n: (n.start, n.pitch))
    return merged


def raw_concat(stem_predictions: list[list[Note]]) -> list[Note]:
    """Concatenate stem predictions without de-duplication."""
    notes: list[Note] = []
    for stem_notes in stem_predictions:
        notes.extend(stem_notes)
    notes.sort(key=lambda n: (n.start, n.pitch))
    return notes

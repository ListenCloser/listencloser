"""Motif/repetition discovery engine.

Detects repeated melodic fragments using interval-sequence matching.
Transposition-invariant: finds motifs that repeat at different pitch levels.

Algorithm:
1. Convert melody notes to interval sequence (semitones)
2. Use sliding window to extract all subsequences of length 3-8
3. Group subsequences by interval pattern (ignoring absolute pitch)
4. Report patterns that appear 2+ times with temporal positions

This is a deterministic, explainable approach suitable for real-time analysis.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Minimum motif length (in notes)
_MIN_MOTIF_LENGTH = 3

# Maximum motif length (in notes)
_MAX_MOTIF_LENGTH = 8

# Minimum occurrences to report
_MIN_OCCURRENCES = 2

# Maximum motifs to return
_MAX_MOTIFS = 10


@dataclass
class MotifNote:
    """A single melody note with temporal information."""
    pitch: int
    start_seconds: float
    end_seconds: float
    note_id: str | None = None


@dataclass
class MotifOccurrence:
    """A single occurrence of a motif."""
    start_seconds: float
    end_seconds: float
    start_pitch: int
    note_ids: list[str] = field(default_factory=list)


@dataclass
class Motif:
    """A discovered motif with all its occurrences."""
    interval_pattern: list[int]  # Semitone intervals
    occurrences: list[MotifOccurrence]
    length: int  # Number of notes

    @property
    def count(self) -> int:
        return len(self.occurrences)

    @property
    def claim(self) -> str:
        """Human-readable description."""
        if self.count == 2:
            return f"Motif of {self.length} notes returns once"
        return f"Motif of {self.length} notes returns {self.count - 1} times"


def discover_motifs(notes: list[MotifNote]) -> list[Motif]:
    """Discover repeated melodic motifs in a note sequence.

    Args:
        notes: Melody notes sorted by start time.

    Returns:
        List of discovered motifs, sorted by occurrence count (descending).
    """
    if len(notes) < _MIN_MOTIF_LENGTH:
        return []

    # Compute interval sequence
    intervals = []
    for i in range(len(notes) - 1):
        interval = notes[i + 1].pitch - notes[i].pitch
        intervals.append(interval)

    # Find all subsequences and group by pattern
    pattern_occurrences: dict[tuple[int, ...], list[int]] = defaultdict(list)

    # length is number of intervals (notes - 1)
    min_intervals = _MIN_MOTIF_LENGTH - 1  # 3 notes = 2 intervals
    max_intervals = min(_MAX_MOTIF_LENGTH - 1, len(intervals))

    for length in range(min_intervals, max_intervals + 1):
        for start_idx in range(len(intervals) - length + 1):
            pattern = tuple(intervals[start_idx:start_idx + length])
            pattern_occurrences[pattern].append(start_idx)

    # Filter to patterns with multiple occurrences
    motifs: list[Motif] = []

    for pattern, start_indices in pattern_occurrences.items():
        if len(start_indices) < _MIN_OCCURRENCES:
            continue

        # Deduplicate overlapping occurrences
        occurrences = _deduplicate_occurrences(notes, pattern, start_indices)

        if len(occurrences) < _MIN_OCCURRENCES:
            continue

        motif = Motif(
            interval_pattern=list(pattern),
            occurrences=occurrences,
            length=len(pattern) + 1,
        )
        motifs.append(motif)

    # Sort by occurrence count (descending), then by length (descending)
    motifs.sort(key=lambda m: (-m.count, -m.length))

    # Remove subsumed motifs (keep only the longest pattern for overlapping regions)
    filtered = _filter_subsumed(motifs)

    return filtered[:_MAX_MOTIFS]


def _deduplicate_occurrences(
    notes: list[MotifNote],
    pattern: tuple[int, ...],
    start_indices: list[int],
) -> list[MotifOccurrence]:
    """Convert start indices to occurrences, deduplicating overlaps."""
    occurrences: list[MotifOccurrence] = []
    last_end = -1.0

    for idx in sorted(start_indices):
        start_note = notes[idx]
        end_note = notes[idx + len(pattern)]

        # Skip if overlapping with previous occurrence
        if start_note.start_seconds < last_end:
            continue

        occurrence = MotifOccurrence(
            start_seconds=start_note.start_seconds,
            end_seconds=end_note.end_seconds,
            start_pitch=start_note.pitch,
            note_ids=[
                notes[i].note_id
                for i in range(idx, idx + len(pattern) + 1)
                if notes[i].note_id
            ],
        )
        occurrences.append(occurrence)
        last_end = end_note.end_seconds

    return occurrences


def _filter_subsumed(motifs: list[Motif]) -> list[Motif]:
    """Remove motifs whose occurrences are subsumed by longer motifs."""
    if len(motifs) <= 1:
        return motifs

    kept: list[Motif] = []
    used_regions: set[tuple[float, float]] = set()

    for motif in motifs:
        # Check if this motif's occurrences are already covered
        new_occurrences = []
        for occ in motif.occurrences:
            region = (occ.start_seconds, occ.end_seconds)
            # Check if this region overlaps with any used region
            is_subsumed = False
            for used in used_regions:
                if (occ.start_seconds >= used[0] and occ.end_seconds <= used[1]):
                    is_subsumed = True
                    break
            if not is_subsumed:
                new_occurrences.append(occ)

        if len(new_occurrences) >= _MIN_OCCURRENCES:
            # Update occurrences to only include non-subsumed ones
            motif.occurrences = new_occurrences
            kept.append(motif)
            # Mark regions as used
            for occ in new_occurrences:
                used_regions.add((occ.start_seconds, occ.end_seconds))

    return kept

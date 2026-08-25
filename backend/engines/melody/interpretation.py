"""Melody interpretation engine.

Derives interpretable musical findings from LStoM melody output:
- Register events (highest/lowest note, large leaps)
- Interval analysis (distribution, stepwise ratio, characteristic intervals)
- Contour segments (ascending/descending/arch patterns)

All findings are temporal with start/end seconds and note provenance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Minimum melody notes required for interpretation
_MIN_NOTES = 5

# Interval thresholds (semitones)
_STEPWISE_THRESHOLD = 2  # ≤ 2 semitones = stepwise
_LEAP_THRESHOLD = 5  # ≥ 5 semitones = leap
_LARGE_LEAP_THRESHOLD = 8  # ≥ 8 semitones = large leap

# Contour segment minimum length
_MIN_CONTOUR_SEGMENT = 4


@dataclass
class MelodyNote:
    """A single melody note with temporal information."""
    pitch: int
    start_seconds: float
    end_seconds: float
    velocity: int = 80
    note_id: str | None = None


@dataclass
class MelodyFinding:
    """A temporal melody finding with provenance."""
    kind: str
    claim: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    evidence: dict = field(default_factory=dict)
    note_ids: list[str] = field(default_factory=list)


def _pitch_name(midi_pitch: int) -> str:
    """Convert MIDI pitch to note name (e.g., 60 → 'C4')."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi_pitch // 12) - 1
    return f"{names[midi_pitch % 12]}{octave}"


def _interval_name(semitones: int) -> str:
    """Convert interval in semitones to musical name."""
    names = {
        0: "unison",
        1: "minor 2nd",
        2: "major 2nd",
        3: "minor 3rd",
        4: "major 3rd",
        5: "perfect 4th",
        6: "tritone",
        7: "perfect 5th",
        8: "minor 6th",
        9: "major 6th",
        10: "minor 7th",
        11: "major 7th",
        12: "octave",
    }
    return names.get(semitones, f"{semitones} semitones")


def interpret_melody(notes: list[MelodyNote]) -> list[MelodyFinding]:
    """Derive interpretable findings from a melody note sequence.

    Args:
        notes: Melody notes sorted by start time.

    Returns:
        List of temporal findings with provenance.
    """
    if len(notes) < _MIN_NOTES:
        return []

    findings: list[MelodyFinding] = []

    # ── Register events ─────────────────────────────────────────────────
    pitches = [n.pitch for n in notes]
    high_idx = pitches.index(max(pitches))
    low_idx = pitches.index(min(pitches))

    findings.append(MelodyFinding(
        kind="melody_register_peak",
        claim=f"Highest melody note: {_pitch_name(notes[high_idx].pitch)}",
        start_seconds=notes[high_idx].start_seconds,
        end_seconds=notes[high_idx].end_seconds,
        evidence={
            "pitch": notes[high_idx].pitch,
            "pitch_name": _pitch_name(notes[high_idx].pitch),
            "type": "highest",
        },
        note_ids=[notes[high_idx].note_id] if notes[high_idx].note_id else [],
    ))

    findings.append(MelodyFinding(
        kind="melody_register_low",
        claim=f"Lowest melody note: {_pitch_name(notes[low_idx].pitch)}",
        start_seconds=notes[low_idx].start_seconds,
        end_seconds=notes[low_idx].end_seconds,
        evidence={
            "pitch": notes[low_idx].pitch,
            "pitch_name": _pitch_name(notes[low_idx].pitch),
            "type": "lowest",
        },
        note_ids=[notes[low_idx].note_id] if notes[low_idx].note_id else [],
    ))

    # ── Interval analysis ───────────────────────────────────────────────
    intervals = []
    for i in range(len(notes) - 1):
        interval = abs(notes[i + 1].pitch - notes[i].pitch)
        direction = "ascending" if notes[i + 1].pitch > notes[i].pitch else (
            "descending" if notes[i + 1].pitch < notes[i].pitch else "static"
        )
        intervals.append({
            "semitones": interval,
            "direction": direction,
            "start_seconds": notes[i].start_seconds,
            "end_seconds": notes[i + 1].end_seconds,
            "from_note_id": notes[i].note_id,
            "to_note_id": notes[i + 1].note_id,
        })

    # Interval distribution
    nonzero = [iv["semitones"] for iv in intervals if iv["semitones"] > 0]
    if nonzero:
        stepwise_count = sum(1 for iv in nonzero if iv <= _STEPWISE_THRESHOLD)
        leap_count = sum(1 for iv in nonzero if iv >= _LEAP_THRESHOLD)
        stepwise_ratio = round(stepwise_count / len(nonzero), 3)
        leap_ratio = round(leap_count / len(nonzero), 3)

        findings.append(MelodyFinding(
            kind="melody_interval_summary",
            claim=f"{round(stepwise_ratio * 100)}% stepwise, {round(leap_ratio * 100)}% leaps",
            evidence={
                "stepwise_ratio": stepwise_ratio,
                "leap_ratio": leap_ratio,
                "total_intervals": len(nonzero),
                "stepwise_count": stepwise_count,
                "leap_count": leap_count,
            },
        ))

    # Largest leap
    large_leaps = [iv for iv in intervals if iv["semitones"] >= _LARGE_LEAP_THRESHOLD]
    if large_leaps:
        largest = max(large_leaps, key=lambda iv: iv["semitones"])
        findings.append(MelodyFinding(
            kind="melody_large_leap",
            claim=(
                f"Largest leap: {_interval_name(largest['semitones'])} "
                f"({largest['direction']}) at {largest['start_seconds']:.1f}s"
            ),
            start_seconds=largest["start_seconds"],
            end_seconds=largest["end_seconds"],
            evidence={
                "semitones": largest["semitones"],
                "direction": largest["direction"],
                "interval_name": _interval_name(largest["semitones"]),
            },
            note_ids=[nid for nid in [largest["from_note_id"], largest["to_note_id"]] if nid],
        ))

    # Most common interval
    if nonzero:
        from collections import Counter
        interval_counts = Counter(nonzero)
        most_common_interval = interval_counts.most_common(1)[0]
        ic_semitones, ic_count = most_common_interval
        if ic_count >= 3:  # Only report if it appears 3+ times
            findings.append(MelodyFinding(
                kind="melody_characteristic_interval",
                claim=(
                    f"Most common interval: {_interval_name(ic_semitones)} "
                    f"({ic_count} occurrences)"
                ),
                evidence={
                    "semitones": ic_semitones,
                    "interval_name": _interval_name(ic_semitones),
                    "count": ic_count,
                    "total_intervals": len(nonzero),
                },
            ))

    # ── Contour segments ────────────────────────────────────────────────
    contour_segments = _detect_contour_segments(notes)
    for segment in contour_segments[:5]:  # Limit to 5 segments
        findings.append(segment)

    return findings


def _detect_contour_segments(notes: list[MelodyNote]) -> list[MelodyFinding]:
    """Detect contour segments (ascending, descending, arch, etc.).

    Uses a sliding window approach to identify sustained directional motion.
    """
    if len(notes) < _MIN_CONTOUR_SEGMENT:
        return []

    segments: list[MelodyFinding] = []
    window_size = max(_MIN_CONTOUR_SEGMENT, len(notes) // 8)

    i = 0
    while i <= len(notes) - window_size:
        window = notes[i:i + window_size]
        pitches = [n.pitch for n in window]

        # Calculate contour
        contour = _classify_contour(pitches)

        if contour != "mixed":
            # Find the full extent of this contour
            end_idx = i + window_size
            while end_idx < len(notes):
                extended_pitches = pitches + [notes[end_idx].pitch]
                if _classify_contour(extended_pitches) != contour:
                    break
                pitches = extended_pitches
                end_idx += 1

            start_note = notes[i]
            end_note = notes[end_idx - 1]
            pitch_range = max(pitches) - min(pitches)

            segments.append(MelodyFinding(
                kind=f"melody_contour_{contour}",
                claim=(
                    f"{contour.capitalize()} contour: "
                    f"{_pitch_name(min(pitches))}–{_pitch_name(max(pitches))} "
                    f"({pitch_range} semitones)"
                ),
                start_seconds=start_note.start_seconds,
                end_seconds=end_note.end_seconds,
                evidence={
                    "contour": contour,
                    "start_pitch": pitches[0],
                    "end_pitch": pitches[-1],
                    "pitch_range": pitch_range,
                    "note_count": len(pitches),
                },
                note_ids=[n.note_id for n in notes[i:end_idx] if n.note_id],
            ))

            i = end_idx
        else:
            i += 1

    return segments


def _classify_contour(pitches: list[int]) -> str:
    """Classify the contour of a pitch sequence.

    Returns: 'ascending', 'descending', 'arch', 'inverted_arch', 'static', or 'mixed'
    """
    if len(pitches) < 2:
        return "static"

    # Check if mostly static
    pitch_range = max(pitches) - min(pitches)
    if pitch_range <= 2:
        return "static"

    # Calculate direction changes
    ascending = sum(1 for i in range(len(pitches) - 1) if pitches[i + 1] > pitches[i])
    descending = sum(1 for i in range(len(pitches) - 1) if pitches[i + 1] < pitches[i])
    total = ascending + descending

    if total == 0:
        return "static"

    asc_ratio = ascending / total
    desc_ratio = descending / total

    # Strongly directional
    if asc_ratio > 0.75:
        return "ascending"
    if desc_ratio > 0.75:
        return "descending"

    # Check for arch shape (ascending then descending)
    mid = len(pitches) // 2
    first_half_asc = sum(1 for i in range(mid - 1) if pitches[i + 1] > pitches[i])
    second_half_desc = sum(1 for i in range(mid, len(pitches) - 1) if pitches[i + 1] < pitches[i])

    if first_half_asc > mid * 0.6 and second_half_desc > (len(pitches) - mid) * 0.6:
        return "arch"

    # Check for inverted arch (descending then ascending)
    first_half_desc = sum(1 for i in range(mid - 1) if pitches[i + 1] < pitches[i])
    second_half_asc = sum(1 for i in range(mid, len(pitches) - 1) if pitches[i + 1] > pitches[i])

    if first_half_desc > mid * 0.6 and second_half_asc > (len(pitches) - mid) * 0.6:
        return "inverted_arch"

    return "mixed"

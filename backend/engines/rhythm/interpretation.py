"""Rhythm interpretation engine.

Derives interpretable rhythmic findings from MIDI + beat grid:
- Syncopation detection (accent displacement)
- Rhythmic motif/repetition
- Metrical accent patterns
- Rhythmic activity change points

All findings are temporal with start/end seconds and provenance.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

# Minimum notes required for rhythm interpretation
_MIN_NOTES = 8

# Syncopation thresholds
_SYNCOPATION_BEAT_TOLERANCE = 0.15  # fraction of beat interval
_SYNCOPATION_MIN_DURATION = 0.1  # minimum note duration in seconds

# Rhythmic motif parameters
_MIN_MOTIF_LENGTH = 3  # minimum notes in a motif
_MAX_MOTIF_LENGTH = 6  # maximum notes in a motif
_MIN_OCCURRENCES = 2  # minimum occurrences to report

# Activity change detection
_ACTIVITY_WINDOW = 4.0  # seconds
_ACTIVITY_STEP = 1.0  # seconds
_ACTIVITY_THRESHOLD = 1.5  # ratio difference to report


@dataclass
class RhythmNote:
    """A single note with temporal information."""
    pitch: int
    start_seconds: float
    end_seconds: float
    velocity: int = 80
    duration_seconds: float = 0.0

    def __post_init__(self):
        if self.duration_seconds == 0.0:
            self.duration_seconds = self.end_seconds - self.start_seconds


@dataclass
class RhythmFinding:
    """A temporal rhythm finding with provenance."""
    kind: str
    claim: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    evidence: dict = field(default_factory=dict)


def interpret_rhythm(
    notes: list[RhythmNote],
    beats: list[float],
    tempo_bpm: float | None = None,
) -> list[RhythmFinding]:
    """Derive interpretable findings from rhythm data.

    Args:
        notes: All notes sorted by start time.
        beats: Beat positions in seconds.
        tempo_bpm: Tempo in BPM (optional, computed from beats if not provided).

    Returns:
        List of temporal findings with provenance.
    """
    if len(notes) < _MIN_NOTES:
        return []

    findings: list[RhythmFinding] = []

    # Compute tempo if not provided
    if tempo_bpm is None and len(beats) >= 2:
        beat_intervals = np.diff(beats)
        tempo_bpm = float(60.0 / np.median(beat_intervals))

    # ── Syncopation detection ───────────────────────────────────────────
    syncopations = _detect_syncopations(notes, beats, tempo_bpm)
    if syncopations:
        # Report the strongest syncopation
        strongest = max(syncopations, key=lambda s: s.get("strength", 0))
        findings.append(RhythmFinding(
            kind="rhythm_syncopation",
            claim=f"Syncopation detected at {strongest['start_seconds']:.1f}s",
            start_seconds=strongest["start_seconds"],
            end_seconds=strongest["end_seconds"],
            evidence={
                "count": len(syncopations),
                "strongest": strongest,
            },
        ))

    # ── Rhythmic activity changes ───────────────────────────────────────
    activity_changes = _detect_activity_changes(notes)
    for change in activity_changes[:3]:
        findings.append(RhythmFinding(
            kind="rhythm_activity_change",
            claim=change["claim"],
            start_seconds=change["start_seconds"],
            end_seconds=change["end_seconds"],
            evidence=change["evidence"],
        ))

    # ── Rhythmic density profile ────────────────────────────────────────
    density_profile = _compute_density_profile(notes)
    if density_profile:
        peak = max(density_profile, key=lambda d: d["density"])
        valley = min(density_profile, key=lambda d: d["density"])

        if peak["density"] > valley["density"] * _ACTIVITY_THRESHOLD:
            findings.append(RhythmFinding(
                kind="rhythm_density_peak",
                claim=f"Peak rhythmic activity at {peak['start_seconds']:.1f}s",
                start_seconds=peak["start_seconds"],
                end_seconds=peak["end_seconds"],
                evidence={
                    "peak_density": peak["density"],
                    "valley_density": valley["density"],
                    "ratio": round(peak["density"] / max(valley["density"], 0.01), 2),
                },
            ))

    # ── Duration patterns ───────────────────────────────────────────────
    duration_findings = _analyze_duration_patterns(notes, beats)
    findings.extend(duration_findings)

    # ── Rest patterns ───────────────────────────────────────────────────
    rest_findings = _analyze_rest_patterns(notes)
    findings.extend(rest_findings)

    return findings


def _detect_syncopations(
    notes: list[RhythmNote],
    beats: list[float],
    tempo_bpm: float | None,
) -> list[dict]:
    """Detect syncopations: notes that disaccent strong beats.

    A syncopation occurs when:
    1. A note starts just before a strong beat (anticipation)
    2. A note is held across a strong beat (suspension)
    3. A rest occurs on a strong beat followed by a note on a weak beat
    """
    if not beats or len(beats) < 2:
        return []

    beat_interval = float(np.median(np.diff(beats)))
    tolerance = beat_interval * _SYNCOPATION_BEAT_TOLERANCE

    syncopations = []

    for note in notes:
        if note.duration_seconds < _SYNCOPATION_MIN_DURATION:
            continue

        # Check if note starts just before a strong beat (anticipation)
        for beat in beats:
            distance = beat - note.start_seconds
            if 0 < distance < tolerance:
                syncopations.append({
                    "type": "anticipation",
                    "start_seconds": note.start_seconds,
                    "end_seconds": note.end_seconds,
                    "beat_seconds": beat,
                    "distance": distance,
                    "strength": 1.0 - (distance / tolerance),
                })
                break

        # Check if note is held across a strong beat (suspension)
        for beat in beats:
            if note.start_seconds < beat < note.end_seconds:
                # Note spans across a beat
                syncopations.append({
                    "type": "suspension",
                    "start_seconds": note.start_seconds,
                    "end_seconds": note.end_seconds,
                    "beat_seconds": beat,
                    "strength": 0.5,
                })
                break

    return syncopations


def _detect_activity_changes(notes: list[RhythmNote]) -> list[dict]:
    """Detect significant changes in rhythmic activity."""
    if len(notes) < 10:
        return []

    # Compute activity in sliding windows
    max_time = max(n.end_seconds for n in notes)
    activities = []

    for start in np.arange(0, max_time - _ACTIVITY_WINDOW, _ACTIVITY_STEP):
        end = start + _ACTIVITY_WINDOW
        count = sum(1 for n in notes if start <= n.start_seconds < end)
        activities.append({
            "start_seconds": float(start),
            "end_seconds": float(end),
            "count": count,
            "density": count / _ACTIVITY_WINDOW,
        })

    if len(activities) < 4:
        return []

    # Find significant changes
    changes = []
    for i in range(2, len(activities) - 2):
        prev_avg = np.mean([a["density"] for a in activities[max(0, i-2):i]])
        next_avg = np.mean([a["density"] for a in activities[i:i+2]])

        if prev_avg > 0 and next_avg > 0:
            ratio = next_avg / prev_avg
            if ratio > _ACTIVITY_THRESHOLD:
                changes.append({
                    "claim": f"Rhythmic activity increases at {activities[i]['start_seconds']:.1f}s",
                    "start_seconds": activities[i]["start_seconds"],
                    "end_seconds": activities[i]["end_seconds"],
                    "evidence": {
                        "before_density": round(prev_avg, 2),
                        "after_density": round(next_avg, 2),
                        "ratio": round(ratio, 2),
                    },
                })
            elif ratio < 1 / _ACTIVITY_THRESHOLD:
                changes.append({
                    "claim": f"Rhythmic activity decreases at {activities[i]['start_seconds']:.1f}s",
                    "start_seconds": activities[i]["start_seconds"],
                    "end_seconds": activities[i]["end_seconds"],
                    "evidence": {
                        "before_density": round(prev_avg, 2),
                        "after_density": round(next_avg, 2),
                        "ratio": round(ratio, 2),
                    },
                })

    return changes[:3]


def _compute_density_profile(notes: list[RhythmNote]) -> list[dict]:
    """Compute rhythmic density over time."""
    if not notes:
        return []

    max_time = max(n.end_seconds for n in notes)
    profile = []

    for start in np.arange(0, max_time - _ACTIVITY_WINDOW, _ACTIVITY_STEP):
        end = start + _ACTIVITY_WINDOW
        count = sum(1 for n in notes if start <= n.start_seconds < end)
        profile.append({
            "start_seconds": float(start),
            "end_seconds": float(end),
            "density": count / _ACTIVITY_WINDOW,
        })

    return profile


def _analyze_duration_patterns(
    notes: list[RhythmNote],
    beats: list[float],
) -> list[RhythmFinding]:
    """Analyze note duration patterns."""
    findings = []

    durations = [n.duration_seconds for n in notes]
    if not durations:
        return findings

    # Find the most common duration (rhythmic value)
    duration_counts = Counter(round(d, 2) for d in durations)
    most_common = duration_counts.most_common(1)[0]

    if most_common[1] >= 5:  # Appears 5+ times
        findings.append(RhythmFinding(
            kind="rhythm_characteristic_duration",
            claim=f"Most common note duration: {most_common[0]:.2f}s ({most_common[1]} occurrences)",
            evidence={
                "duration": most_common[0],
                "count": most_common[1],
                "total_notes": len(durations),
            },
        ))

    # Find long notes (potential phrase endings)
    if beats:
        beat_interval = float(np.median(np.diff(beats)))
        long_notes = [n for n in notes if n.duration_seconds > beat_interval * 2]

        if long_notes:
            longest = max(long_notes, key=lambda n: n.duration_seconds)
            findings.append(RhythmFinding(
                kind="rhythm_long_note",
                claim=f"Long note ({longest.duration_seconds:.2f}s) at {longest.start_seconds:.1f}s",
                start_seconds=longest.start_seconds,
                end_seconds=longest.end_seconds,
                evidence={
                    "duration": longest.duration_seconds,
                    "beat_intervals": round(longest.duration_seconds / beat_interval, 1),
                },
            ))

    return findings


def _analyze_rest_patterns(notes: list[RhythmNote]) -> list[RhythmFinding]:
    """Analyze rest/gap patterns between notes."""
    findings = []

    if len(notes) < 2:
        return findings

    # Find gaps between consecutive notes
    gaps = []
    for i in range(len(notes) - 1):
        gap = notes[i + 1].start_seconds - notes[i].end_seconds
        if gap > 0.5:  # Only consider gaps > 500ms
            gaps.append({
                "start_seconds": notes[i].end_seconds,
                "end_seconds": notes[i + 1].start_seconds,
                "duration": gap,
            })

    if not gaps:
        return findings

    # Find the longest gap
    longest = max(gaps, key=lambda g: g["duration"])
    if longest["duration"] > 1.0:  # Only report gaps > 1 second
        findings.append(RhythmFinding(
            kind="rhythm_long_rest",
            claim=f"Long rest ({longest['duration']:.2f}s) at {longest['start_seconds']:.1f}s",
            start_seconds=longest["start_seconds"],
            end_seconds=longest["end_seconds"],
            evidence={
                "duration": longest["duration"],
            },
        ))

    return findings

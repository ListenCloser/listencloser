"""Reusable transcription forensics (evaluation/debug oriented, not UI).

Operates on a list of note dicts (``pitch``, ``start``, ``end``, ``velocity``,
optional ``amplitude``) so it can inspect both canonical notes and raw model
note events.  Produces the diagnostics used in the #214/#215 forensics.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

C2 = 36
C7 = 96


def _notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(notes, key=lambda n: (n["start"], n["pitch"]))


def note_stats(notes: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute the forensic metrics for a list of note dicts."""
    ns = _notes(notes)
    pitches = [int(n["pitch"]) for n in ns]
    durs = [float(n["end"]) - float(n["start"]) for n in ns]
    vels = [int(n.get("velocity", 64)) for n in ns]

    # amplitude (if present)
    amps = [n["amplitude"] for n in ns if n.get("amplitude") is not None]

    # very short notes
    short = {t: sum(1 for d in durs if d < t) for t in (0.05, 0.1, 0.15)}

    # local pitch isolation: >12 semitones from nearest note within +-500ms
    isolated = 0
    for i, n in enumerate(ns):
        p, s = int(n["pitch"]), float(n["start"])
        nearest = None
        for j, m in enumerate(ns):
            if i == j:
                continue
            if abs(float(m["start"]) - s) <= 0.5:
                d = abs(int(m["pitch"]) - p)
                if nearest is None or d < nearest:
                    nearest = d
        if nearest is not None and nearest > 12:
            isolated += 1

    # same-pitch fragments within 100ms
    repeated = 0
    by_pitch: dict[int, list[float]] = {}
    for n in ns:
        by_pitch.setdefault(int(n["pitch"]), []).append(float(n["start"]))
    for starts in by_pitch.values():
        starts.sort()
        for a, b in zip(starts, starts[1:], strict=False):
            if b - a < 0.1:
                repeated += 1

    # polyphony distribution (10ms bins)
    max_t = max((float(n["end"]) for n in ns), default=0.0)
    bins = int(max_t / 0.01) + 1
    active = [0] * bins
    for n in ns:
        s = int(float(n["start"]) / 0.01)
        e = int(float(n["end"]) / 0.01) + 1
        for b in range(max(0, s), min(bins, e)):
            active[b] += 1
    polyphony = dict(sorted(Counter(active).items()))

    return {
        "note_count": len(ns),
        "min_pitch": min(pitches) if pitches else None,
        "max_pitch": max(pitches) if pitches else None,
        "above_C7": sum(1 for p in pitches if p > C7),
        "below_C2": sum(1 for p in pitches if p < C2),
        "shorter_50ms": short[0.05],
        "shorter_100ms": short[0.1],
        "shorter_150ms": short[0.15],
        "isolated_gt12": isolated,
        "repeated_100ms": repeated,
        "pitch_histogram": dict(sorted(Counter(pitches).items())),
        "duration_histogram_ms": dict(sorted(Counter(round(d * 1000) for d in durs).items())),
        "amplitude_distribution": _histogram(amps, 10),
        "velocity_histogram": dict(sorted(Counter(round(v, -1) for v in vels).items())),
        "velocity_min": min(vels) if vels else None,
        "velocity_max": max(vels) if vels else None,
        "duration_min_ms": round(min(durs) * 1000, 1) if durs else None,
        "duration_max_ms": round(max(durs) * 1000, 1) if durs else None,
        "polyphony": polyphony,
    }


def _histogram(values: list[float], bins: int) -> dict[str, int]:
    if not values:
        return {}
    lo, hi = min(values), max(values)
    if hi <= lo:
        return {round(lo, 3): len(values)}
    edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    counts = Counter()
    for v in values:
        for i in range(bins):
            if v <= edges[i + 1] or i == bins - 1:
                counts[round(edges[i], 3)] += 1
                break
    return dict(sorted(counts.items()))

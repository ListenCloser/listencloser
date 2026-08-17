"""Metrical grid from beat/downbeat positions.

Builds a structured grid with inferred meter, measure boundaries, and
per-measure candidate subdivision grids. When downbeats are absent, the
grid remains beat-aware but does not invent meter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MetricalGrid:
    beats: list[float]
    downbeats: list[float] | None
    beat_positions: list[int] | None
    measure_boundaries: list[float]
    inferred_meter: tuple[int, int] | None
    heuristic_confidence: float
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_count": len(self.beats),
            "downbeat_count": len(self.downbeats) if self.downbeats else 0,
            "measure_count": len(self.measure_boundaries),
            "inferred_meter": (
                f"{self.inferred_meter[0]}/{self.inferred_meter[1]}"
                if self.inferred_meter
                else None
            ),
            "heuristic_confidence": round(self.heuristic_confidence, 3),
            "provenance": self.provenance,
        }

    def global_beats(self) -> bool:
        return len(self.beats) >= 2


def build_metrical_grid(
    beats: list[float],
    downbeats: list[float] | None = None,
    beat_positions: list[int] | None = None,
) -> MetricalGrid:
    if len(beats) < 2:
        return MetricalGrid(
            beats=beats,
            downbeats=downbeats,
            beat_positions=beat_positions,
            measure_boundaries=[],
            inferred_meter=None,
            heuristic_confidence=0.0,
        )

    if downbeats and len(downbeats) >= 2:
        boundaries = _snap_to_beat_grid(downbeats, beats)
        meter = _infer_meter(beats, boundaries)
        heuristic_confidence = 0.8 if len(boundaries) >= 3 else 0.5
    else:
        boundaries = []
        meter = None
        heuristic_confidence = 0.0

    return MetricalGrid(
        beats=beats,
        downbeats=downbeats,
        beat_positions=beat_positions,
        measure_boundaries=boundaries,
        inferred_meter=meter,
        heuristic_confidence=heuristic_confidence,
    )


def _snap_to_beat_grid(downbeats: list[float], beats: list[float]) -> list[float]:
    """Snap downbeat positions to the regular beat grid.

    Beat trackers return jittered timestamps; a measure boundary that is not an
    exact multiple of the beat interval (e.g. 4.02 s on a 0.5 s grid) forces the
    quantizer into sub-tactus step sizes that music21 cannot engrave to
    MusicXML. Meter is only claimed when boundaries land cleanly on the beat
    grid.
    """
    if not downbeats:
        return []
    beat_sorted = sorted(float(b) for b in beats if b >= 0)
    if len(beat_sorted) < 2:
        return []
    intervals = np.diff(np.asarray(beat_sorted))
    intervals = intervals[intervals > 0]
    if intervals.size == 0:
        return []
    beat_interval = float(np.median(intervals))
    anchor = float(downbeats[0])

    snapped: list[float] = []
    for d in downbeats:
        position = round((float(d) - anchor) / beat_interval) * beat_interval + anchor
        if not snapped or position - snapped[-1] > beat_interval / 2:
            snapped.append(position)
    return snapped


def _infer_meter(beats: list[float], downbeats: list[float]) -> tuple[int, int] | None:
    db_sorted = sorted(downbeats)
    beat_sorted = sorted(beats)
    counts: list[int] = []
    for i in range(len(db_sorted) - 1):
        count = sum(1 for b in beat_sorted if db_sorted[i] <= b < db_sorted[i + 1])
        if 2 <= count <= 12:
            counts.append(count)
    if not counts:
        return None
    from collections import Counter

    bpb = Counter(counts).most_common(1)[0][0]
    if bpb == 2:
        return (2, 4)
    if bpb == 3:
        return (3, 4)
    if bpb == 4:
        return (4, 4)
    if bpb == 6:
        # Ambiguous: could be compound duple (6/8) or 6/4.
        # Mark 6/8 as heuristic — beat trackers may report
        # subdivision pulses rather than tactus beats.
        return (6, 8)
    return None


def _median_interval(times: list[float]) -> float:
    intervals = np.diff(np.asarray(times, dtype=float))
    return float(np.median(intervals[intervals > 0])) if intervals.size > 0 else 0.5


def measure_boundary_end(i: int, boundaries: list[float], beats: list[float]) -> float:
    if i + 1 < len(boundaries):
        return boundaries[i + 1]
    if not boundaries:
        return beats[-1] + _median_interval(beats)
    spans = [b2 - b1 for b1, b2 in zip(boundaries, boundaries[1:], strict=False)]
    typical = float(np.median(spans)) if spans else _median_interval(beats)
    return boundaries[-1] + typical

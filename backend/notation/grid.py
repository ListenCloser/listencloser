"""Metrical grid from beat/downbeat positions.

Builds a structured grid with inferred meter, measure boundaries, and
beat indices. Falls back gracefully when downbeat information is absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MetricalGrid:
    beats: list[float]
    downbeats: list[float] | None
    beat_positions: list[int]
    measure_boundaries: list[float]
    inferred_meter: tuple[int, int] | None
    confidence: float
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
            "confidence": round(self.confidence, 3),
            "provenance": self.provenance,
        }

    def subdivisions(self, candidate: tuple[int, int] = (4, 4)) -> list[list[float]]:
        """Return subdivision candidate grids for each measure.

        Each inner list is the floating-point grid positions
        (quarter, eighth, triplet, sixteenth) covering that measure.
        """
        grids: list[list[float]] = []
        for i, start in enumerate(self.measure_boundaries):
            end = (
                self.measure_boundaries[i + 1]
                if i + 1 < len(self.measure_boundaries)
                else self.beats[-1] + _median_interval(self.beats)
            )
            grids.append(_build_candidate_grids(start, end, candidate))
        return grids


def build_metrical_grid(
    beats: list[float],
    downbeats: list[float] | None = None,
    beat_positions: list[int] | None = None,
) -> MetricalGrid:
    if len(beats) < 2:
        return MetricalGrid(
            beats=beats,
            downbeats=downbeats,
            beat_positions=beat_positions or list(range(len(beats))),
            measure_boundaries=[beats[0]] if beats else [],
            inferred_meter=None,
            confidence=0.0,
        )

    if downbeats and len(downbeats) >= 2:
        boundaries = list(downbeats)
        beats_per_bar = _estimate_beats_per_bar(downbeats, beats)
        confidence = 0.8 if len(boundaries) >= 3 else 0.5
    else:
        beats_per_bar = 4
        boundaries = [beats[i] for i in range(0, len(beats), beats_per_bar)]
        confidence = 0.3

    meter: tuple[int, int] | None = (beats_per_bar, 4) if beats_per_bar in (2, 3, 4, 6) else None

    return MetricalGrid(
        beats=beats,
        downbeats=downbeats,
        beat_positions=beat_positions or list(range(len(beats))),
        measure_boundaries=boundaries,
        inferred_meter=meter,
        confidence=confidence,
    )


def _estimate_beats_per_bar(downbeats: list[float], beats: list[float]) -> int:
    db_times = sorted(downbeats)
    beat_times = sorted(beats)
    counts: list[int] = []
    for i in range(len(db_times) - 1):
        count = sum(1 for b in beat_times if db_times[i] <= b < db_times[i + 1])
        if 2 <= count <= 12:
            counts.append(count)
    if not counts:
        return 4
    from collections import Counter

    return Counter(counts).most_common(1)[0][0]


def _median_interval(times: list[float]) -> float:
    intervals = np.diff(np.asarray(times, dtype=float))
    return float(np.median(intervals[intervals > 0])) if intervals.size > 0 else 0.5


def _build_candidate_grids(
    measure_start: float, measure_end: float, meter: tuple[int, int]
) -> list[float]:
    dur = measure_end - measure_start
    if dur <= 0:
        return [measure_start]
    beat_dur = dur / meter[0]
    grids: list[float] = [measure_start]
    for b in range(meter[0]):
        beat_start = measure_start + b * beat_dur
        grids.append(beat_start)
        grids.append(beat_start + beat_dur * 0.5)
        grids.append(beat_start + beat_dur * 0.25)
        grids.append(beat_start + beat_dur * 0.75)
        grids.append(beat_start + beat_dur * 0.3333)
        grids.append(beat_start + beat_dur * 0.6667)
    grids.append(measure_end)
    return sorted(set(grids))

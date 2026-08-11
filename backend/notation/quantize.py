"""Adaptive, measure-aware quantization for notation MIDI.

Each measure selects the simplest candidate grid that explains the
performed timing well enough, using a cost function over all notes
in that measure. Performance MIDI is never modified.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from notation.grid import MetricalGrid, _median_interval, measure_boundary_end

CANDIDATES = [
    ("quarter", 0.25),
    ("eighth", 0.125),
    ("triplet_eighth", 0.08333),
    ("sixteenth", 0.0625),
]


def adaptive_quantize(
    midi_bytes: bytes,
    grid: MetricalGrid,
) -> tuple[bytes, dict[str, Any]]:
    import io

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    report: dict[str, Any] = _fresh_report(grid)

    if not grid.global_beats():
        return _fail_honest(midi, report)

    if grid.inferred_meter is None or not grid.measure_boundaries:
        return _fail_honest(midi, report)

    measures = _collect_notes_by_measure(midi, grid)
    selections: list[dict[str, Any]] = []

    for m_idx, notes in enumerate(measures):
        if not notes:
            continue
        m_start = grid.measure_boundaries[m_idx]
        m_end = measure_boundary_end(m_idx, grid.measure_boundaries, grid.beats)
        sel = _select_grid_for_measure(notes, m_start, m_end)
        selections.append(sel)
        for note in notes:
            note.start = sel["grid"](note.start_t)
            note.end = sel["grid"](note.end_t)
            if note.end <= note.start:
                note.end = note.start + _min_duration(grid)

    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        instrument.notes.sort(key=lambda n: (n.start, n.pitch, n.end))

    report["timing_mode"] = "metrical_grid"
    report["grid_selections"] = selections
    report["quantized_notes"] = _count_quantized(selections)
    report["onset_movement_sum"] = round(
        sum(s["avg_movement"] * s["note_count"] for s in selections), 4
    )
    report["onset_movement_max"] = round(
        max((s["max_movement"] for s in selections), default=0.0), 4
    )

    return _encode(midi), report


def _fresh_report(grid: MetricalGrid) -> dict[str, Any]:
    return {
        "profile": "adaptive_metrical_v2",
        "beat_count": len(grid.beats),
        "measure_count": len(grid.measure_boundaries),
        "quantized_notes": 0,
        "onset_movement_sum": 0.0,
        "onset_movement_max": 0.0,
        "grid_selections": [],
    }


def _fail_honest(midi: Any, report: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    report["timing_mode"] = "preserved_no_grid"
    return _encode(midi), report


def _encode(midi: Any) -> bytes:
    import io

    out = io.BytesIO()
    midi.write(out)
    return out.getvalue()


class _QNote:
    __slots__ = ("pitch", "start", "end", "start_t", "end_t")

    def __init__(self, note: Any) -> None:
        self.pitch = note.pitch
        self.start = note.start
        self.end = note.end
        self.start_t = float(note.start)
        self.end_t = float(note.end)


def _collect_notes_by_measure(midi: Any, grid: MetricalGrid) -> list[list[_QNote]]:
    measures: list[list[_QNote]] = [[] for _ in grid.measure_boundaries]
    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            m_idx = _measure_index(note.start, grid)
            if 0 <= m_idx < len(measures):
                measures[m_idx].append(_QNote(note))
    return measures


def _select_grid_for_measure(
    notes: list[_QNote],
    m_start: float,
    m_end: float,
) -> dict[str, Any]:
    best_grid_name = "eighth"
    best_cost = float("inf")
    best_fn = lambda v: v  # noqa: E731

    for name, step in CANDIDATES:
        g = _build_grid(m_start, m_end, step)
        fn = lambda v, g=g: _nearest(g, v)  # noqa: E731
        cost, movement = _grid_cost_for_notes(notes, fn)
        if cost < best_cost:
            best_cost = cost
            best_grid_name = name
            best_fn = fn
            best_movement = movement

    return {
        "measure_index": _measure_index(notes[0].start_t, None) if notes else 0,
        "grid_name": best_grid_name,
        "note_count": len(notes),
        "cost": round(best_cost, 4),
        "avg_movement": round(best_movement["avg"], 6) if best_movement else 0.0,
        "max_movement": round(best_movement["max"], 6) if best_movement else 0.0,
        "grid": best_fn,
    }


def _grid_cost_for_notes(
    notes: list[_QNote],
    grid_fn,
) -> tuple[float, dict[str, float]]:
    onset_errs: list[float] = []
    dur_errs: list[float] = []
    for n in notes:
        o = grid_fn(n.start_t)
        e = grid_fn(n.end_t)
        if e <= o:
            return float("inf"), {"avg": 0, "max": 0}
        onset_errs.append(abs(o - n.start_t))
        dur_errs.append(abs((e - o) - (n.end_t - n.start_t)))
    avg_onset = float(np.mean(onset_errs)) if onset_errs else 0.0
    avg_dur = float(np.mean(dur_errs)) if dur_errs else 0.0
    max_onset = float(np.max(onset_errs)) if onset_errs else 0.0
    return (
        avg_onset * 8.0 + avg_dur * 5.0 + _complexity_penalty(len(notes), step_of(grid_fn)),
        {"avg": avg_onset, "max": max_onset},
    )


def _complexity_penalty(note_count: int, step: float) -> float:
    if step >= 0.24:
        return 0.0
    if step >= 0.12:
        return 0.3
    if step >= 0.08:
        return 0.8
    return 1.2


def step_of(fn) -> float:
    """Heuristic: infer step size from the grid function, used for complexity."""
    try:
        g = fn(0.0)
        g2 = fn(0.0 + 1e-6)
        return abs(g2 - g)
    except Exception:
        return 0.125


def _build_grid(start: float, end: float, step: float) -> list[float]:
    pts = []
    t = start
    while t <= end + 1e-9:
        pts.append(t)
        t += step
    if abs(pts[-1] - end) > 1e-9:
        pts.append(end)
    return sorted(set(pts))


def _nearest(grid: list[float], value: float) -> float:
    import bisect

    idx = bisect.bisect_left(grid, value)
    nearby = grid[max(0, idx - 1) : min(len(grid), idx + 2)]
    return min(nearby, key=lambda c: abs(c - value)) if nearby else value


def _measure_index(onset: float, grid: MetricalGrid | None) -> int:
    if grid is None:
        return 0
    for i, m_start in enumerate(grid.measure_boundaries):
        next_start = measure_boundary_end(i, grid.measure_boundaries, grid.beats)
        if m_start <= onset < next_start:
            return i
    return 0


def _min_duration(grid: MetricalGrid) -> float:
    return max(_median_interval(grid.beats) / 4, 0.05)


def _count_quantized(selections: list[dict[str, Any]]) -> int:
    return sum(s.get("note_count", 0) for s in selections)

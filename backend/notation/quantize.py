"""Adaptive, measure-aware quantization for notation MIDI.

Each measure selects the simplest candidate grid that explains the
performed timing well enough, using a cost function over all notes
in that measure. Candidate grids are anchored to the measure boundary.

Performance MIDI is never modified.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from notation.grid import MetricalGrid, _median_interval, measure_boundary_end


def adaptive_quantize(
    midi_bytes: bytes,
    grid: MetricalGrid,
) -> tuple[bytes, dict[str, Any]]:
    import io

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    report: dict[str, Any] = _fresh_report(grid)

    if not grid.global_beats():
        return _fail_honest(midi, report, "preserved_no_grid")

    if grid.inferred_meter is None or not grid.measure_boundaries:
        return _fail_honest(midi, report, "preserved_no_meter")

    measures = _collect_notes_by_measure(midi, grid)
    selections: list[dict[str, Any]] = []

    for m_idx, notes in enumerate(measures):
        if not notes:
            continue
        m_start = grid.measure_boundaries[m_idx]
        m_end = measure_boundary_end(m_idx, grid.measure_boundaries, grid.beats)
        bpm = grid.inferred_meter[0]
        sel = _select_grid_for_measure(notes, m_start, m_end, bpm, m_idx)
        selections.append(sel)
        quantize_fn = _build_quantizer_from_step(m_start, m_end, sel["step_seconds"])
        for qn in notes:
            new_start = quantize_fn(qn.start_t)
            new_end = quantize_fn(qn.end_t)
            if new_end <= new_start:
                new_end = new_start + _min_duration(grid)
            qn.note.start = new_start
            qn.note.end = new_end

    report["timing_mode"] = "metrical_grid"
    report["grid_selections"] = selections
    report["quantized_notes"] = _count_changed(selections)
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


def _fail_honest(
    midi: Any,
    report: dict[str, Any],
    mode: str,
) -> tuple[bytes, dict[str, Any]]:
    report["timing_mode"] = mode
    return _encode(midi), report


def _encode(midi: Any) -> bytes:
    import io

    out = io.BytesIO()
    midi.write(out)
    return out.getvalue()


class _QNote:
    __slots__ = ("note", "start_t", "end_t")

    def __init__(self, note: Any) -> None:
        self.note = note
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
    beats_per_measure: int,
    m_idx: int,
) -> dict[str, Any]:
    dur = m_end - m_start
    if dur <= 0:
        return _fallback_selection(m_idx, len(notes))

    beat_dur = dur / max(beats_per_measure, 1)
    candidates = [
        ("quarter", beat_dur),
        ("eighth", beat_dur / 2),
        ("triplet_eighth", beat_dur / 3),
        ("sixteenth", beat_dur / 4),
    ]

    best_name = "eighth"
    best_step = beat_dur / 2
    best_cost = float("inf")
    best_movement = {"avg": 0.0, "max": 0.0}
    best_changed = 0

    for name, step in candidates:
        fn = _build_quantizer_from_step(m_start, m_end, step)
        cost, movement, changed = _grid_cost_for_notes(notes, fn, name)
        if cost < best_cost:
            best_cost = cost
            best_name = name
            best_step = step
            best_movement = movement
            best_changed = changed

    return {
        "measure_index": m_idx,
        "grid_name": best_name,
        "step_seconds": round(best_step, 6),
        "note_count": len(notes),
        "changed_count": best_changed,
        "cost": round(best_cost, 4),
        "avg_movement": round(best_movement["avg"], 6),
        "max_movement": round(best_movement["max"], 6),
    }


def _fallback_selection(m_idx: int, count: int) -> dict[str, Any]:
    return {
        "measure_index": m_idx,
        "grid_name": "fallback",
        "step_seconds": 0.125,
        "note_count": count,
        "changed_count": 0,
        "cost": 999,
        "avg_movement": 0.0,
        "max_movement": 0.0,
    }


def _grid_cost_for_notes(
    notes: list[_QNote],
    quantize_fn,
    grid_name: str,
) -> tuple[float, dict[str, float], int]:
    onset_errs: list[float] = []
    changed = 0
    for n in notes:
        o = quantize_fn(n.start_t)
        e = quantize_fn(n.end_t)
        if e <= o:
            return float("inf"), {"avg": 0, "max": 0}, 0
        if abs(o - n.start_t) > 1e-9 or abs(e - n.end_t) > 1e-9:
            changed += 1
        onset_errs.append(abs(o - n.start_t))
    avg_onset = float(np.mean(onset_errs)) if onset_errs else 0.0
    max_onset = float(np.max(onset_errs)) if onset_errs else 0.0
    complexity = _complexity_penalty(grid_name, len(notes))
    return (
        avg_onset * 8.0 + complexity,
        {"avg": avg_onset, "max": max_onset},
        changed,
    )


def _complexity_penalty(grid_name: str, note_count: int) -> float:
    base = {"quarter": 0.0, "eighth": 0.3, "triplet_eighth": 0.8, "sixteenth": 1.2}.get(
        grid_name, 2.0
    )
    return base * (1.0 + note_count * 0.01)


def _build_quantizer_from_step(m_start: float, m_end: float, step: float):
    """Build a quantizer with grid positions anchored at m_start."""
    pts = []
    t = m_start
    while t <= m_end + step * 0.5:
        pts.append(t)
        t += step
    grid = sorted(set(pts))
    import bisect

    def fn(value: float) -> float:
        idx = bisect.bisect_left(grid, value)
        nearby = grid[max(0, idx - 1) : min(len(grid), idx + 2)]
        return min(nearby, key=lambda c: abs(c - value)) if nearby else value

    return fn


def _measure_index(onset: float, grid: MetricalGrid) -> int:
    for i, m_start in enumerate(grid.measure_boundaries):
        next_start = measure_boundary_end(i, grid.measure_boundaries, grid.beats)
        if m_start <= onset < next_start:
            return i
    return 0


def _min_duration(grid: MetricalGrid) -> float:
    return max(_median_interval(grid.beats) / 4, 0.05)


def _count_changed(selections: list[dict[str, Any]]) -> int:
    return sum(s.get("changed_count", 0) for s in selections)

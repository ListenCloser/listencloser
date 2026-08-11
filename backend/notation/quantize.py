"""Adaptive, measure-aware quantization for notation MIDI.

Per-measure candidate grids are evaluated with an explicit cost function
that balances timing error against notation complexity.

Performance MIDI is never modified.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from notation.grid import MetricalGrid, measure_boundary_end


def adaptive_quantize(
    midi_bytes: bytes,
    grid: MetricalGrid,
) -> tuple[bytes, dict[str, Any]]:
    """Quantize performance MIDI using a metrical grid.

    Each measure selects the simplest candidate grid that explains the
    performed timing well enough, using a cost function balancing onset
    error, duration error, and rhythmic complexity penalties.
    """
    import io

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    report: dict[str, Any] = {
        "profile": "adaptive_metrical_v2",
        "beat_count": len(grid.beats),
        "measure_count": len(grid.measure_boundaries),
        "quantized_notes": 0,
        "onset_movement_sum": 0.0,
        "onset_movement_max": 0.0,
        "grid_selections": [],
    }

    if not grid.global_beats():
        return _fail_honest(midi, report, "preserved_no_grid")

    if grid.inferred_meter is None or not grid.measure_boundaries:
        return _fail_honest(midi, report, "preserved_no_meter")

    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            start, end = _quantize_note(note.start, note.end, grid)
            if start != note.start or end != note.end:
                report["quantized_notes"] = int(report["quantized_notes"]) + 1
                report["onset_movement_sum"] = round(
                    float(report["onset_movement_sum"]) + abs(start - note.start), 4
                )
                report["onset_movement_max"] = round(
                    max(float(report["onset_movement_max"]), abs(start - note.start)), 4
                )
            if end <= start:
                end = start + _min_duration(grid)
            note.start, note.end = start, end
        instrument.notes.sort(key=lambda n: (n.start, n.pitch, n.end))

    return _encode(midi), report


def _fail_honest(midi: Any, report: dict[str, Any], mode: str) -> tuple[bytes, dict[str, Any]]:
    report["timing_mode"] = mode
    return _encode(midi), report


def _encode(midi: Any) -> bytes:
    import io

    out = io.BytesIO()
    midi.write(out)
    return out.getvalue()


def _quantize_note(onset: float, end: float, grid: MetricalGrid) -> tuple[float, float]:
    meter = grid.inferred_meter
    if meter is None:
        return onset, end

    m_idx = _measure_index(onset, grid)
    m_start = grid.measure_boundaries[m_idx]
    m_end = measure_boundary_end(m_idx, grid.measure_boundaries, grid.beats)

    # Find measure(s) spanned by the note
    e_idx = _measure_index(end, grid)
    if e_idx < 0:
        e_idx = len(grid.measure_boundaries) - 1

    if m_idx == e_idx:
        new_onset, new_end = _quantize_span(onset, end, m_start, m_end, meter)
    else:
        new_onset, _ = _quantize_span(onset, onset, m_start, m_end, meter)
        e_start = grid.measure_boundaries[e_idx] if e_idx < len(grid.measure_boundaries) else m_end
        e_end = measure_boundary_end(e_idx, grid.measure_boundaries, grid.beats)
        _, new_end = _quantize_span(end, end, e_start, e_end, meter)

    if new_end <= new_onset:
        new_end = new_onset + _min_duration(grid)
    return new_onset, new_end


def _quantize_span(
    onset: float,
    end: float,
    m_start: float,
    m_end: float,
    meter: tuple[int, int],
) -> tuple[float, float]:
    """Quantize onset and end using the best candidate grid for this measure."""
    candidates = _candidate_grids(m_start, m_end, meter)
    best_grid = _select_grid(onset, end, candidates)
    return _nearest(best_grid, onset), _nearest(best_grid, end)


def _candidate_grids(
    m_start: float,
    m_end: float,
    meter: tuple[int, int],
) -> list[tuple[str, list[float]]]:
    dur = m_end - m_start
    if dur <= 0:
        return [("fallback", [m_start])]
    beat_dur = dur / meter[0]
    grids: list[tuple[str, list[float]]] = []
    # Straight grids
    grids.append(("eighth", _build(m_start, m_end, beat_dur / 2)))
    grids.append(("sixteenth", _build(m_start, m_end, beat_dur / 4)))
    # Triplet
    grids.append(("triplet_eighth", _build(m_start, m_end, beat_dur / 3)))
    # Quarter
    grids.append(("quarter", _build(m_start, m_end, beat_dur)))
    return grids


def _build(start: float, end: float, step: float) -> list[float]:
    pts = []
    t = start
    while t <= end + 1e-9:
        pts.append(t)
        t += step
    if abs(pts[-1] - end) > 1e-9:
        pts.append(end)
    return sorted(set(pts))


def _select_grid(
    onset: float,
    end: float,
    candidates: list[tuple[str, list[float]]],
) -> list[float]:
    best_cost = float("inf")
    best_grid = candidates[0][1]
    for name, g in candidates:
        c = _grid_cost(onset, end, g, name)
        if c < best_cost:
            best_cost = c
            best_grid = g
    return best_grid


def _grid_cost(
    onset: float,
    end: float,
    grid: list[float],
    name: str,
) -> float:
    o_start = _nearest(grid, onset)
    o_end = _nearest(grid, end)
    if o_end <= o_start:
        return float("inf")
    onset_err = abs(o_start - onset)
    dur_err = abs((o_end - o_start) - (end - onset))
    complexity = {
        "quarter": 0.0,
        "eighth": 1.0,
        "triplet_eighth": 2.0,
        "sixteenth": 1.5,
    }.get(name, 2.0)
    tiny = 1.0 if (o_end - o_start) < 0.04 else 0.0
    return onset_err * 10.0 + dur_err * 5.0 + complexity * 0.02 + tiny * 20.0


def _nearest(grid: list[float], value: float) -> float:
    idx = int(np.searchsorted(grid, value))
    nearby = grid[max(0, idx - 1) : min(len(grid), idx + 2)]
    return min(nearby, key=lambda c: abs(c - value)) if nearby else value


def _measure_index(onset: float, grid: MetricalGrid) -> int:
    for i, m_start in enumerate(grid.measure_boundaries):
        next_start = measure_boundary_end(i, grid.measure_boundaries, grid.beats)
        if m_start <= onset < next_start:
            return i
    return 0


def _min_duration(grid: MetricalGrid) -> float:
    import numpy as np

    intervals = np.diff(np.asarray(grid.beats, dtype=float))
    median = float(np.median(intervals[intervals > 0])) if intervals.size > 0 else 0.5
    return max(median / 4, 0.05)

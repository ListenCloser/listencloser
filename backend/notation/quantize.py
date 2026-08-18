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
    """Quantize note endpoints independently against their containing measure.

    Two-pass design:

    Pass 1 selects a grid for every trustworthy measure before mutating any note.
    A measure's grid is chosen from the onsets of the notes that begin there (and
    the releases that end inside it); a release that lies in a later measure is
    never scored against the onset measure's bounded grid, so sustained notes do
    not bias the subdivision of the measure they begin in.

    Pass 2 quantizes each temporal endpoint using the grid of the measure that
    contains it. An endpoint that lands exactly on a measure boundary is snapped
    to that boundary. Endpoints outside a trustworthy measured region are
    preserved rather than mapped to an unrelated measure.

    The quantizer still outputs one logical note per input note (start < end, full
    musical sustain preserved); barline ties are owned downstream.
    """
    import io

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    report: dict[str, Any] = _fresh_report(grid)

    if not grid.global_beats():
        return _fail_honest(midi, report, "preserved_no_grid")

    if grid.inferred_meter is None or not grid.measure_boundaries:
        return _fail_honest(midi, report, "preserved_no_meter")

    all_notes = _collect_all_notes(midi, grid)
    beats_per_measure = grid.inferred_meter[0]

    # Pass 1: select a grid for every usable measure before mutating any note.
    selections: list[dict[str, Any]] = []
    measure_quantizers: list[Any | None] = []
    for m_idx in range(len(grid.measure_boundaries)):
        m_start = grid.measure_boundaries[m_idx]
        m_end = measure_boundary_end(m_idx, grid.measure_boundaries, grid.beats)
        onset_notes = [qn for qn in all_notes if _measure_index(qn.start_t, grid) == m_idx]
        if not onset_notes:
            measure_quantizers.append(None)
            continue
        sel = _select_grid_for_measure(onset_notes, m_start, m_end, beats_per_measure, m_idx)
        selections.append(sel)
        measure_quantizers.append(_build_quantizer_from_step(m_start, m_end, sel["step_seconds"]))

    # Pass 2: quantize temporal endpoints independently.
    for qn in all_notes:
        start_midx = _measure_index(qn.start_t, grid)
        end_midx = _measure_index(qn.end_t, grid)

        new_start = qn.start_t
        if start_midx is not None and measure_quantizers[start_midx] is not None:
            new_start = measure_quantizers[start_midx](qn.start_t)

        boundary = _snap_to_measure_boundary(qn.end_t, grid.measure_boundaries)
        if boundary is not None:
            new_end = boundary
        elif end_midx is not None and measure_quantizers[end_midx] is not None:
            new_end = measure_quantizers[end_midx](qn.end_t)
        else:
            new_end = qn.end_t

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


def _collect_all_notes(midi: Any, grid: MetricalGrid) -> list[_QNote]:
    notes: list[_QNote] = []
    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            notes.append(_QNote(note))
    return notes


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
        cost, movement, changed = _grid_cost_for_notes(notes, fn, name, m_start, m_end)
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
    m_start: float,
    m_end: float,
) -> tuple[float, dict[str, float], int]:
    onset_errs: list[float] = []
    changed = 0
    for n in notes:
        o = quantize_fn(n.start_t)
        if abs(o - n.start_t) > 1e-9:
            changed += 1
        onset_errs.append(abs(o - n.start_t))
        # A release is scored against this measure only when it lies inside it.
        # Releases in a later measure (or before the measure) must not bias the
        # onset measure's grid selection toward an incorrect subdivision.
        if m_start < n.end_t < m_end:
            e = quantize_fn(n.end_t)
            if e <= o:
                return float("inf"), {"avg": 0, "max": 0}, 0
            if abs(e - n.end_t) > 1e-9:
                changed += 1
            onset_errs.append(abs(e - n.end_t))
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


def _measure_index(onset: float, grid: MetricalGrid) -> int | None:
    """Return the measure containing ``onset``, or ``None`` when it lies outside
    every known measure (before the first boundary or past the last inferred
    measure). Callers must treat ``None`` as "outside a trustworthy metrical
    region" and preserve the endpoint rather than mapping it to measure 0.
    """
    for i, m_start in enumerate(grid.measure_boundaries):
        next_start = measure_boundary_end(i, grid.measure_boundaries, grid.beats)
        if m_start <= onset < next_start:
            return i
    return None


def _snap_to_measure_boundary(
    value: float, boundaries: list[float], eps: float = 1e-6
) -> float | None:
    """Snap a value to an exact measure boundary when it lands on one."""
    for b in boundaries:
        if abs(value - b) <= eps:
            return b
    return None


def _min_duration(grid: MetricalGrid) -> float:
    return max(_median_interval(grid.beats) / 4, 0.05)


def quantize_fixed_grid(
    midi_bytes: bytes,
    bpm: float | None = None,
    subdivision: int = 2,
) -> tuple[bytes, dict[str, Any]]:
    """Quantize note onsets/offsets to a fixed rhythmic grid.

    Used when beat/downbeat tracking is unavailable or inconsistent with the
    MIDI's own tempo. A fixed eighth-note grid (subdivision=2) anchored to the
    MIDI tempo produces clean, readable durations instead of raw performance
    micro-timing. Returns ``(midi_bytes, report)``.
    """
    import io

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    if bpm is None:
        tempo_changes = midi.get_tempo_changes()
        bpm = float(tempo_changes[1][0]) if tempo_changes[1] else 120.0
    step = 60.0 / bpm / subdivision

    for instrument in midi.instruments:
        for note in instrument.notes:
            start = round(float(note.start) / step) * step
            end = round(float(note.end) / step) * step
            if end <= start:
                end = start + step
            note.start = start
            note.end = end

    out = io.BytesIO()
    midi.write(out)
    report: dict[str, Any] = {
        "profile": "fixed_grid_v1",
        "timing_mode": "fixed_grid",
        "bpm": round(bpm, 3),
        "subdivision": subdivision,
        "grid_step_seconds": round(step, 4),
        "quantized_notes": sum(len(i.notes) for i in midi.instruments),
    }
    return out.getvalue(), report


# ---------------------------------------------------------------------------
# Evidence-based rhythmic grid selection
# ---------------------------------------------------------------------------

# (name, subdivision factor, complexity prior). ``factor`` divides the beat:
# quarter=1, eighth=2, triplet-eighth=3, sixteenth=4. The complexity prior is a
# fixed simplicity preference for coarser grids (kept small so a finer grid is
# chosen when timing evidence clearly favours it).
RHYTHMIC_CANDIDATES: tuple[tuple[str, float, float], ...] = (
    ("quarter", 1.0, 0.0),
    ("eighth", 2.0, 0.2),
    ("triplet_eighth", 3.0, 0.5),
    ("sixteenth", 4.0, 0.8),
)

# When notes fall exactly between two candidate grids this is the tie-break
# toward the finer grid; it is bounded below so a coarse grid is not chosen just
# to hide a noisy onset cloud.
_SNAP_EPSILON = 1e-6


def quantize_rhythmic_grid(
    midi_bytes: bytes,
    bpm: float | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Quantize to the simplest rhythmic grid that explains the performance.

    Tries quarter, eighth, triplet-eighth and sixteenth grids anchored to the
    MIDI's own tempo, scoring each on onset/duration displacement, notation
    fragmentation (distinct durations), and a simplicity prior. Returns
    ``(midi_bytes, report)`` with the selected subdivision and diagnostics.
    """
    import io

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    if bpm is None:
        tempo_changes = midi.get_tempo_changes()
        bpm = float(tempo_changes[1][0]) if tempo_changes[1] else 120.0
    beat = 60.0 / bpm

    notes = [
        (note, float(note.start), float(note.end))
        for instrument in midi.instruments
        if not instrument.is_drum
        for note in instrument.notes
    ]

    # A note is "misaligned" if it sits more than 5% of a beat off the grid;
    # deliberate off-beat rhythms keep many notes misaligned on a coarse grid,
    # whereas transcription noise affects only a few.
    epsilon = beat * 0.05

    best: dict[str, Any] | None = None
    candidate_costs: dict[str, float] = {}
    for name, factor, complexity in RHYTHMIC_CANDIDATES:
        step = beat / factor
        cost, metrics = _evaluate_candidate(notes, step, complexity, epsilon)
        candidate_costs[name] = round(cost, 6)
        if best is None or cost < best["cost"]:
            best = {
                "name": name,
                "factor": factor,
                "step": step,
                "cost": cost,
                "metrics": metrics,
            }

    chosen = best or {
        "name": "eighth",
        "factor": 2.0,
        "step": beat / 2.0,
        "cost": 0.0,
        "metrics": {},
    }
    step = chosen["step"]

    onset_shifts: list[float] = []
    duration_shifts: list[float] = []
    for note, start, end in notes:
        new_start = round(start / step) * step
        new_end = round(end / step) * step
        if new_end <= new_start + _SNAP_EPSILON:
            new_end = new_start + step
        onset_shifts.append(abs(new_start - start))
        duration_shifts.append(abs((new_end - new_start) - (end - start)))
        note.start = new_start
        note.end = new_end

    out = io.BytesIO()
    midi.write(out)

    report: dict[str, Any] = {
        "profile": "rhythmic_grid_v1",
        "timing_mode": "rhythmic_grid",
        "bpm": round(bpm, 3),
        "selected_grid": chosen["name"],
        "grid_step_seconds": round(step, 6),
        "candidate_costs": candidate_costs,
        "note_count": len(notes),
        "onset_shift_mean": round(float(np.mean(onset_shifts)) if onset_shifts else 0.0, 6),
        "onset_shift_p95": round(
            float(np.percentile(onset_shifts, 95)) if onset_shifts else 0.0, 6
        ),
        "duration_shift_mean": round(
            float(np.mean(duration_shifts)) if duration_shifts else 0.0, 6
        ),
        "duration_shift_p95": round(
            float(np.percentile(duration_shifts, 95)) if duration_shifts else 0.0, 6
        ),
    }
    return out.getvalue(), report


def _evaluate_candidate(
    notes: list[tuple[Any, float, float]],
    step: float,
    complexity: float,
    epsilon: float,
) -> tuple[float, dict[str, Any]]:
    """Score a candidate grid over all notes.

    Returns ``(cost, metrics)``. The cost combines the fraction of notes left
    misaligned beyond ``epsilon`` (deliberate off-beat rhythms keep many notes
    misaligned on a too-coarse grid), a duration-displacement term, a
    simplicity prior, and a distinct-duration fragmentation penalty. It never
    optimizes for "fewer ties" at the expense of timing.
    """
    misaligned = 0
    duration_rel: list[float] = []
    distinct_durs: set[float] = set()
    for _note, start, end in notes:
        new_start = round(start / step) * step
        new_end = round(end / step) * step
        if new_end <= new_start + _SNAP_EPSILON:
            new_end = new_start + step
        if abs(new_start - start) > epsilon:
            misaligned += 1
        duration_rel.append(abs((new_end - new_start) - (end - start)) / step)
        distinct_durs.add(round((new_end - new_start) / step, 6))

    misalign_frac = misaligned / len(notes) if notes else 0.0
    avg_duration = float(np.mean(duration_rel)) if duration_rel else 0.0
    cost = misalign_frac * 2.0 + avg_duration * 0.5 + complexity + len(distinct_durs) * 0.02
    return cost, {
        "misalign_frac": round(misalign_frac, 6),
        "avg_duration_rel": round(avg_duration, 6),
        "distinct_durations": len(distinct_durs),
        "cost": round(cost, 6),
    }


def _count_changed(selections: list[dict[str, Any]]) -> int:
    return sum(s.get("changed_count", 0) for s in selections)

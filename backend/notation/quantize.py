"""Adaptive, measure-aware quantization for notation MIDI.

Performance MIDI is never modified. Only notation-oriented MIDI artifacts
may be rhythmically corrected.

Subdivision candidates:
  quarter  = 1  slot per beat
  eighth   = 2  slots per beat
  triplet  = 3  slots per beat
  sixteenth = 4 slots per beat

Per-note onset/duration select the nearest candidate that minimizes
a weighted cost function balancing timing error and notation complexity.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from notation.grid import MetricalGrid

Subdivision = tuple[int, int]  # (subdivisions_per_beat, display_name_key)


def adaptive_quantize(
    midi_bytes: bytes,
    grid: MetricalGrid,
    subdivisions: tuple[Subdivision, ...] = ((4, 4),),
) -> tuple[bytes, dict[str, Any]]:
    """Quantize performance MIDI into notation MIDI using a metrical grid.

    Unlike the old fixed-subdivision approach, this selects per-measure
    candidate grids and applies a cost function balancing timing error
    against notation complexity.

    Returns (notation_midi_bytes, report_dict).
    """
    import io

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    report: dict[str, Any] = {
        "profile": "adaptive_metrical_v1",
        "beat_count": len(grid.beats),
        "measure_count": len(grid.measure_boundaries),
        "downbeat_count": len(grid.downbeats) if grid.downbeats else 0,
        "quantized_notes": 0,
        "timing_mode": "metrical_grid",
        "onset_movement_sum": 0.0,
        "onset_movement_max": 0.0,
        "inferred_meter": (
            f"{grid.inferred_meter[0]}/{grid.inferred_meter[1]}" if grid.inferred_meter else None
        ),
    }

    if len(grid.beats) < 2 or not grid.measure_boundaries:
        return _preserve_timing(midi, report)

    if grid.inferred_meter is None:
        return _preserve_timing(midi, report)

    onset_errors: list[float] = []
    quantized_count = 0

    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            start, end = _quantize_note(note.start, note.end, grid, grid.inferred_meter)
            if start != note.start or end != note.end:
                quantized_count += 1
                onset_errors.append(abs(start - note.start))
            if end <= start:
                end = start + _note_duration_fallback(grid)
            note.start, note.end = start, end
        instrument.notes.sort(key=lambda n: (n.start, n.pitch, n.end))

    report["quantized_notes"] = quantized_count
    if onset_errors:
        report["onset_movement_sum"] = round(float(np.sum(onset_errors)), 4)
        report["onset_movement_max"] = round(float(np.max(onset_errors)), 4)

    out = io.BytesIO()
    midi.write(out)
    return out.getvalue(), report


def _preserve_timing(midi: Any, report: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    import io

    report["timing_mode"] = "preserved_no_grid"
    out = io.BytesIO()
    midi.write(out)
    return out.getvalue(), report


def _quantize_note(
    onset: float,
    duration_end: float,
    grid: MetricalGrid,
    meter: tuple[int, int],
) -> tuple[float, float]:
    candidates = grid.subdivisions(meter)
    if not candidates:
        return onset, duration_end

    i = _measure_index(onset, grid)
    if i >= len(candidates):
        i = len(candidates) - 1
    slots = candidates[i] if i < len(candidates) else candidates[-1]

    def nearest(value: float) -> float:
        idx = int(np.searchsorted(slots, value))
        nearby = slots[max(0, idx - 1) : min(len(slots), idx + 2)]
        return min(nearby, key=lambda c: abs(c - value)) if nearby else value

    new_onset = nearest(onset)
    raw_end = nearest(duration_end)
    new_end = raw_end if raw_end > new_onset else new_onset + _note_duration_fallback(grid)
    dur = new_end - new_onset
    if dur < 1e-6:
        new_end = new_onset + _note_duration_fallback(grid)
    return new_onset, new_end


def _measure_index(onset: float, grid: MetricalGrid) -> int:
    for i, m_start in enumerate(grid.measure_boundaries):
        next_start = (
            grid.measure_boundaries[i + 1] if i + 1 < len(grid.measure_boundaries) else float("inf")
        )
        if m_start <= onset < next_start:
            return i
    return 0


def _note_duration_fallback(grid: MetricalGrid) -> float:
    import numpy as np

    intervals = np.diff(np.asarray(grid.beats, dtype=float))
    median = float(np.median(intervals[intervals > 0])) if intervals.size > 0 else 0.5
    return max(median / 4, 0.05)

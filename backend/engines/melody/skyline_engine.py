"""Symbolic melody extraction engine (pretty_midi + custom skyline heuristic).

DEPRECATED: This engine is retained for evaluation baseline comparison only.
Use LStoM (lstom_engine.py) for production melody extraction. The skyline
heuristic has significantly lower accuracy (F1=0.343 vs F1=0.768 on POP909)
and produces contaminated output on classical piano (100% contamination rate).
"""

from __future__ import annotations

import io
import warnings
from typing import Any

import numpy as np
import pretty_midi

from engines.base import EngineProvenance, MelodyEngine, MelodyResult

_HEURISTIC = "greedy_continuity_skyline"


def _pick_melody_note(
    window: list[pretty_midi.Note],
    prev: pretty_midi.Note | None,
) -> tuple[pretty_midi.Note | None, float]:
    """Pick the most melodic candidate from a simultaneous onset group.

    Scores each candidate by: duration (sustained preferred), small leap from
    previous note, and pitch height. Returns (note, score_margin) where margin
    is the gap between the best and second-best candidate score.
    """
    if not window:
        return None, 0.0
    scored: list[tuple[float, pretty_midi.Note]] = []
    for note in window:
        dur = note.end - note.start
        dur_score = min(dur / 2.0, 1.0)  # cap at 2s
        if prev is not None:
            leap = abs(note.pitch - prev.pitch)
            leap_score = 1.0 - min(leap / 12.0, 1.0)
        else:
            leap_score = 0.5
        height_score = (note.pitch - 60) / 48.0
        score = dur_score * 0.5 + leap_score * 0.4 + height_score * 0.1
        scored.append((score, note))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_note = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else best_score
    margin = best_score - second_score
    return best_note, margin


def _midi_melody(midi_input: str | bytes) -> dict[str, Any] | None:
    """Continuity-aware skyline melody heuristic.

    Rather than always picking the highest note at each onset, prefer a
    sustained upper line that minimizes melodic leaps and favors longer,
    overlapping notes. Isolated high spikes are downweighted.

    This is a heuristic for polyphonic transcription, NOT a claim about the
    composer's intended melody. ``midi_input`` may be a file path or raw
    MIDI bytes.
    """
    try:
        if isinstance(midi_input, bytes | bytearray):
            pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_input))
        else:
            pm = pretty_midi.PrettyMIDI(midi_input)
        notes = [note for inst in pm.instruments if not inst.is_drum for note in inst.notes]
        if len(notes) < 2:
            return None
        notes.sort(key=lambda n: (n.start, -n.pitch))

        # Group by onset windows (30 ms) to find competing notes at each time.
        line: list[pretty_midi.Note] = []
        margins: list[float] = []
        i = 0
        while i < len(notes):
            window = [notes[i]]
            j = i + 1
            while j < len(notes) and notes[j].start - notes[i].start < 0.03:
                window.append(notes[j])
                j += 1
            best, margin = _pick_melody_note(window, line[-1] if line else None)
            if best is not None:
                line.append(best)
                margins.append(margin)
            i = j

        if len(line) < 2:
            return None

        intervals = [abs(line[i + 1].pitch - line[i].pitch) for i in range(len(line) - 1)]
        nonzero = [iv for iv in intervals if iv > 0]
        low, high = min(n.pitch for n in line), max(n.pitch for n in line)

        # Quality: average score margin between chosen and runner-up candidates.
        avg_margin = float(np.mean(margins)) if margins else 0.0
        quality_score = round(max(0.0, min(1.0, avg_margin)), 3)

        return {
            "low_pitch": low,
            "high_pitch": high,
            "range_semitones": high - low,
            "unique_pitch_classes": len({n.pitch % 12 for n in line}),
            "stepwise_ratio": round(sum(iv <= 2 for iv in nonzero) / len(nonzero), 3)
            if nonzero
            else 0.0,
            "leap_ratio": (
                round(sum(iv >= 5 for iv in nonzero) / len(nonzero), 3) if nonzero else 0.0
            ),
            "quality_score": quality_score,
            "heuristic": _HEURISTIC,
        }
    except Exception:
        return None


class SkylineMelodyEngine(MelodyEngine):
    ENGINE = "skyline"

    def __init__(self) -> None:
        warnings.warn(
            "SkylineMelodyEngine is deprecated. Use LStoMMelodyEngine for production. "
            "Skyline is retained only for evaluation baseline comparison.",
            DeprecationWarning,
            stacklevel=2,
        )

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_pretty_midi_version(),
            parameters={"heuristic": _HEURISTIC, "deprecated": True},
        )

    def analyze(self, midi_bytes: bytes, **kwargs: Any) -> MelodyResult:
        return MelodyResult(
            melody=_midi_melody(midi_bytes),
            provenance=self.provenance,
        )


def _pretty_midi_version() -> str:
    try:
        return pretty_midi.__version__  # type: ignore[attr-defined]
    except Exception:
        return "unknown"

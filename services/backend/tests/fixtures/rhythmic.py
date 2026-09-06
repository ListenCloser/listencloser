"""Deterministic rhythmic MIDI fixtures for notation-quality tests.

Each fixture encodes an exact intended rhythm at 120 BPM so a quantizer's
subdivision selection can be verified against a ground truth. ``beat`` is a
quarter note (0.5 s); a step of ``beat/n`` is the n-th subdivision.
"""

from __future__ import annotations

import io

import pretty_midi

BEAT = 0.5  # quarter note at 120 BPM


def _midi_from_onsets(onsets: list[float], durations: list[float], pitches: list[int]) -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    instrument = pretty_midi.Instrument(program=0)
    for onset, duration, pitch in zip(onsets, durations, pitches, strict=False):
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=pitch, start=onset, end=onset + duration)
        )
    midi.instruments.append(instrument)
    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def straight_eighths() -> bytes:
    """A simple ascending line in straight eighth notes."""
    step = BEAT / 2
    onsets = [i * step for i in range(16)]
    durations = [step] * 16
    pitches = [60 + (i % 8) for i in range(16)]
    return _midi_from_onsets(onsets, durations, pitches)


def sixteenth_notes() -> bytes:
    """A line that requires a sixteenth-note grid (four per beat)."""
    step = BEAT / 4
    onsets = [i * step for i in range(16)]
    durations = [step] * 16
    pitches = [60 + (i % 8) for i in range(16)]
    return _midi_from_onsets(onsets, durations, pitches)


def triplet_eighths() -> bytes:
    """A line in triplet eighths (three per beat)."""
    step = BEAT / 3
    onsets = [i * step for i in range(12)]
    durations = [step] * 12
    pitches = [60 + (i % 8) for i in range(12)]
    return _midi_from_onsets(onsets, durations, pitches)


def dotted_rhythm() -> bytes:
    """A dotted-eighth / sixteenth pattern (3 + 1 subdivision per beat)."""
    dotted = BEAT / 2 * 1.5  # dotted eighth = 0.375 s
    sixteenth = BEAT / 4
    onsets: list[float] = []
    durations: list[float] = []
    pitches: list[int] = []
    t = 0.0
    pitch = 60
    for _ in range(8):
        onsets.append(t)
        durations.append(dotted)
        pitches.append(pitch)
        onsets.append(t + dotted)
        durations.append(sixteenth)
        pitches.append(pitch + 2)
        t += BEAT
    return _midi_from_onsets(onsets, durations, pitches)


ALL_FIXTURES = {
    "straight_eighths": straight_eighths,
    "sixteenth_notes": sixteenth_notes,
    "triplet_eighths": triplet_eighths,
    "dotted_rhythm": dotted_rhythm,
}

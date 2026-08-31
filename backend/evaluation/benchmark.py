"""Shared reference-MIDI conversion retained from the retired benchmark runner.

The generic threshold-sweep and cleanup-ablation orchestration that originally
lived in this module was consumed and removed. ``_midi_to_notes`` remains only
because the shared engine-evaluation path uses the same canonical ``Note``
conversion when scoring reference MIDI.
"""

from __future__ import annotations

import io

import pretty_midi

from evaluation.transcription_metrics import Note


def _midi_to_notes(midi_bytes: bytes) -> list[Note]:
    """Convert reference MIDI bytes into canonical non-drum note records."""
    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    return [
        Note(pitch=n.pitch, start=n.start, end=n.end, velocity=n.velocity)
        for inst in pm.instruments
        for n in inst.notes
        if not inst.is_drum
    ]

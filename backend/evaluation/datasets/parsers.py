"""Reference-annotation parsers for GuitarSet and BabySlakh.

Each parser converts a dataset's native annotation format into the common
note-event list used by the evaluation metrics:
  {"pitch": int, "start": float, "end": float, "velocity": int}
"""

from __future__ import annotations

from typing import Any


def parse_guitarset_jams(jams_json: str) -> list[dict[str, Any]]:
    """Parse a GuitarSet JAMS annotation into note events.

    GuitarSet stores per-string ``note_midi`` annotations whose ``value`` is a
    fractional MIDI pitch (intonation). We round to the nearest integer pitch
    and merge all strings into one note list.
    """
    import json

    doc = json.loads(jams_json)
    notes: list[dict[str, Any]] = []
    for ann in doc.get("annotations", []):
        if ann.get("namespace") != "note_midi":
            continue
        for obs in ann.get("data", []):
            value = obs.get("value")
            if value is None:
                continue
            pitch = int(round(float(value)))
            notes.append(
                {
                    "pitch": pitch,
                    "start": float(obs.get("time", 0.0)),
                    "end": float(obs.get("time", 0.0)) + float(obs.get("duration", 0.0)),
                    "velocity": 80,
                }
            )
    notes.sort(key=lambda n: (n["start"], n["pitch"]))
    return notes


def parse_babyslakh_midi(midi_bytes: bytes, exclude_drums: bool = True) -> list[dict[str, Any]]:
    """Parse a BabySlakh/Slakh ``all_src.mid`` into note events.

    Drum tracks (``is_drum``) are excluded by default so pitched-note metrics
    are not polluted by percussion.
    """
    import io

    import pretty_midi

    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    notes: list[dict[str, Any]] = []
    for inst in pm.instruments:
        if exclude_drums and inst.is_drum:
            continue
        for note in inst.notes:
            notes.append(
                {
                    "pitch": note.pitch,
                    "start": note.start,
                    "end": note.end,
                    "velocity": note.velocity,
                }
            )
    notes.sort(key=lambda n: (n["start"], n["pitch"]))
    return notes

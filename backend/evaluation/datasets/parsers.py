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


# Chord-quality labels GuitarSet uses in the first ``chord`` annotation,
# mapped to the compact quality strings the analysis pipeline expects.
_CHORD_QUALITY_MAP = {
    "maj": "M",
    "min": "m",
    "dim": "dim",
    "aug": "aug",
    "7": "7",
    "maj7": "maj7",
    "min7": "min7",
    "sus2": "sus2",
    "sus4": "sus4",
}


def parse_guitarset_harmony(jams_json: str) -> dict[str, Any]:
    """Extract the GuitarSet harmony reference (chords + key/mode) from JAMS.

    GuitarSet ships two ``chord`` annotations and one ``key_mode`` annotation.
    The first ``chord`` annotation uses the compact ``Root:quality`` form
    (e.g. ``D#:maj``); the second adds slash-bass and extension syntax
    (e.g. ``D#:sus2(7)/1``). We consume the first annotation for scoring and
    the ``key_mode`` annotation for key ground truth.

    Returns:
        {
          "chords": [
            {"root": str, "quality": str, "start": float, "end": float, "label": str},
            ...
          ],
          "key": {"tonic": str, "mode": str, "label": str, "confidence": float},
        }
    """
    import json

    doc = json.loads(jams_json)
    chords: list[dict[str, Any]] = []
    key: dict[str, Any] = {}
    for ann in doc.get("annotations", []):
        namespace = ann.get("namespace")
        if namespace == "chord" and not chords:
            for obs in ann.get("data", []):
                label = str(obs.get("value", ""))
                start = float(obs.get("time", 0.0))
                end = start + float(obs.get("duration", 0.0))
                root, quality = _split_chord_label(label)
                if not root:
                    continue
                chords.append(
                    {
                        "root": root,
                        "quality": quality,
                        "start": round(start, 3),
                        "end": round(end, 3),
                        "label": label,
                    }
                )
        elif namespace == "key_mode" and not key:
            obs = ann.get("data", [{}])[0]
            label = str(obs.get("value", ""))
            tonic, mode = _split_key_label(label)
            key = {
                "tonic": tonic,
                "mode": mode,
                "label": label,
                "confidence": float(obs.get("confidence") or 0.0),
            }
    return {"chords": chords, "key": key}


def _split_chord_label(label: str) -> tuple[str | None, str]:
    """Split a GuitarSet chord label like ``D#:maj`` into (root, quality).

    Roots are normalized to the flat spelling GuitarSet uses in ``key_mode``
    (``Eb`` for the chord the key calls ``Eb``) so root comparisons between
    chords and keys are consistent. Quality is mapped to the compact forms the
    analysis pipeline expects; unrecognized qualities fall back to the raw
    suffix.
    """
    if ":" not in label:
        return None, ""
    root_raw, quality_raw = label.split(":", 1)
    if not root_raw:
        return None, ""
    root = _SHARP_TO_FLAT.get(root_raw, root_raw)
    quality = _CHORD_QUALITY_MAP.get(quality_raw, quality_raw)
    return root, quality


_SHARP_TO_FLAT = {
    "C#": "Db",
    "D#": "Eb",
    "F#": "Gb",
    "G#": "Ab",
    "A#": "Bb",
}


def _split_key_label(label: str) -> tuple[str, str]:
    """Split a GuitarSet key label like ``Eb:major`` into (tonic, mode)."""
    if ":" not in label:
        return label, "major"
    tonic, mode = label.split(":", 1)
    return tonic, mode


def build_guitarset_reference_midi(notes: list[dict[str, Any]]) -> bytes:
    """Build a reference MIDI file from parsed JAMS note events.

    Used so symbolic harmony engines (music21) have an input when the dataset
    does not ship a reference MIDI but does ship note annotations.
    """
    import io

    import pretty_midi

    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    inst = pretty_midi.Instrument(program=0, is_drum=False)
    for note in notes:
        inst.notes.append(
            pretty_midi.Note(
                velocity=int(note.get("velocity", 80)),
                pitch=int(note["pitch"]),
                start=float(note["start"]),
                end=float(note["end"]),
            )
        )
    pm.instruments.append(inst)
    buf = io.BytesIO()
    pm.write(buf)
    return buf.getvalue()


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

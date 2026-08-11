"""Corpus loading and validation helpers."""

from __future__ import annotations

import json
import os
from typing import Any

from .models import CorpusManifest, EvalClip


def load_manifest(path: str) -> CorpusManifest:
    """Load a corpus manifest from a JSON file."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Manifest not found: {path}")
    return CorpusManifest.from_file(path)


def validate_clip_fixtures(clip: EvalClip) -> list[str]:
    """Check that referenced fixtures exist. Returns list of issues."""
    issues: list[str] = []
    if not os.path.isfile(clip.audio):
        issues.append(f"audio file missing: {clip.audio}")
    if clip.reference_midi and not os.path.isfile(clip.reference_midi):
        issues.append(f"reference MIDI missing: {clip.reference_midi}")
    return issues


def build_piano_synthetic_fixture(target_dir: str) -> None:
    """Generate a small synthetic MIDI + WAV fixture for evaluation."""
    import math
    import struct
    import wave

    os.makedirs(target_dir, exist_ok=True)

    sr = 22050
    duration = 2.0
    num_samples = int(sr * duration)

    def sine(freq: float, t: float) -> float:
        return math.sin(2 * math.pi * freq * t) * 0.3

    samples: list[float] = []
    for i in range(num_samples):
        t = i / sr
        val = sine(261.63, t) + sine(329.63, t) + sine(392.00, t)
        if t > 0.5:
            val += sine(349.23, t) + sine(440.00, t) + sine(523.25, t)
        if t < 0.02 or (t - int(t)) < 0.01:
            val *= 0.1
        samples.append(val)

    max_val = max(abs(s) for s in samples) or 1
    scaled = [int(s / max_val * 30000) for s in samples]
    wav_path = os.path.join(target_dir, "piano-synthetic.wav")
    with wave.open(wav_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for sample in scaled:
            wf.writeframes(struct.pack("<h", sample))

    midi_path = os.path.join(target_dir, "piano-synthetic.mid")
    _write_simple_midi(
        midi_path,
        [
            (60, 0.0, 0.5, 64),
            (64, 0.0, 0.5, 64),
            (67, 0.0, 0.5, 64),
            (65, 0.5, 0.5, 64),
            (69, 0.5, 0.5, 64),
            (72, 0.5, 0.5, 64),
            (60, 1.0, 0.5, 64),
            (64, 1.0, 0.5, 64),
            (67, 1.0, 0.5, 64),
            (65, 1.5, 0.5, 64),
            (69, 1.5, 0.5, 64),
            (72, 1.5, 0.5, 64),
        ],
    )

    manifest_path = os.path.join(target_dir, "manifest.json")
    manifest_data: dict[str, Any] = {
        "name": "synthetic_piano",
        "description": "Synthetic C-E-G then F-A-C piano arpeggios for deterministic evaluation.",
        "clips": [
            {
                "id": "piano_synthetic",
                "audio": "piano-synthetic.wav",
                "category": "solo_piano",
                "reference_midi": "piano-synthetic.mid",
                "reference": {"bpm": 120, "key": "C major", "meter": "4/4"},
            }
        ],
    }
    with open(manifest_path, "w") as fh:
        json.dump(manifest_data, fh, indent=2)


def _write_simple_midi(path: str, notes: list[tuple[int, float, float, int]]) -> None:
    """Write a minimal MIDI file (type 0, single track) with the given notes."""
    import struct

    def _var_len(value: int) -> bytes:
        buf = bytearray()
        buf.append(value & 0x7F)
        value >>= 7
        while value:
            buf.append(0x80 | (value & 0x7F))
            value >>= 7
        buf.reverse()
        return bytes(buf)

    def _encode_tempo(bpm: int) -> bytes:
        us_per_beat = int(60_000_000 / bpm)
        return bytes([(us_per_beat >> 16) & 0xFF, (us_per_beat >> 8) & 0xFF, us_per_beat & 0xFF])

    tempo_bpm = 120
    ppq = 480
    ticks_per_sec = ppq * tempo_bpm / 60.0

    class NoteEvent:
        def __init__(self, tick: int, note: int, vel: int, on: bool):
            self.tick = tick
            self.note = note
            self.vel = vel
            self.on = on

    events: list[NoteEvent] = []
    for pitch, start, dur, vel in notes:
        events.append(NoteEvent(int(start * ticks_per_sec), pitch, vel, True))
        events.append(NoteEvent(int((start + dur) * ticks_per_sec), pitch, 0, False))
    events.sort(key=lambda e: e.tick)

    track_data = bytearray()
    # Tempo
    track_data.extend(_var_len(0))
    track_data.extend(bytes([0xFF, 0x51, 0x03]))
    track_data.extend(_encode_tempo(tempo_bpm))

    last_tick = 0
    for ev in events:
        delta = ev.tick - last_tick
        last_tick = ev.tick
        track_data.extend(_var_len(delta))
        cmd = 0x90 if ev.on else 0x80
        track_data.extend(bytes([cmd, ev.note, ev.vel]))

    track_data.extend(_var_len(0))
    track_data.extend(bytes([0xFF, 0x2F, 0x00]))

    header = struct.pack(">HHH", 0, 1, ppq)  # type 0, 1 track
    track_chunk = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)
    midi_data = b"MThd" + struct.pack(">I", 6) + header + track_chunk

    with open(path, "wb") as f:
        f.write(midi_data)

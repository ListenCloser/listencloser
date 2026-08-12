"""Evaluation-only AMT engine adapters.

Each adapter exposes ``transcribe(audio, sr) -> list[Note]`` (canonical Note
representation: MIDI pitch, start seconds, end seconds, velocity). This keeps
engine-specific preprocessing explicit and comparable.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

import numpy as np

from evaluation.transcription_metrics import Note

EngineFn = Callable[[np.ndarray, int], list[Note]]


def _load_wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, audio.astype(np.float32), sr, format="WAV")
    return buf.getvalue()


def basic_pitch_transcribe(
    audio: np.ndarray, sr: int, onset: float = 0.5, frame: float = 0.3
) -> list[Note]:
    """Basic Pitch (Spotify) — general polyphonic AMT, production baseline."""
    import sys
    from pathlib import Path

    backend_dir = str(Path(__file__).resolve().parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from music_features import transcribe_audio

    tr = transcribe_audio(
        _load_wav_bytes(audio, sr), fmt="wav", onset_threshold=onset, frame_threshold=frame
    )
    return [Note.from_dict(n) for n in tr.get("notes", [])]


def byte_piano_transcribe(audio: np.ndarray, sr: int) -> list[Note]:
    """ByteDance high-resolution piano transcription (piano specialist).

    Trained on MAESTRO v2 (solo piano). NOT applicable to guitar/full-mix.
    """
    from piano_transcription_inference import PianoTranscription, sample_rate

    data = np.asarray(audio, dtype=np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != sample_rate:
        import librosa

        data = librosa.resample(data, orig_sr=sr, target_sr=sample_rate)

    transcriptor = PianoTranscription(device="cpu")
    import os
    import tempfile

    tmp = tempfile.mkdtemp(prefix="amt_")
    midi_path = os.path.join(tmp, "out.mid")
    result = transcriptor.transcribe(data, midi_path)

    notes: list[Note] = []
    for ev in result.get("est_note_events", []):
        notes.append(
            Note(
                pitch=int(ev["midi_note"]),
                start=float(ev["onset_time"]),
                end=float(ev["offset_time"]),
                velocity=int(ev.get("velocity", 80)),
            )
        )
    return notes


ENGINES: dict[str, dict[str, Any]] = {
    "basic_pitch": {
        "fn": basic_pitch_transcribe,
        "label": "Basic Pitch (general)",
        "scope": ["guitar", "full_mix", "piano_stem"],
    },
    "byte_piano": {
        "fn": byte_piano_transcribe,
        "label": "ByteDance piano (specialist)",
        "scope": ["piano_stem"],
    },
}

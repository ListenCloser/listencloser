"""Deterministic excerpt slicing utilities for the evaluation corpus.

Each utility slices a source artifact to a [start, end) time window and rebases
timestamps so the excerpt starts at time 0. All timestamps are seconds.
"""

from __future__ import annotations

from typing import Any

# Clamp to keep floating point differences from producing negative durations.
_EPSILON = 1e-6


def rebase(times: list[float], start: float) -> list[float]:
    """Rebase a list of absolute timestamps to be relative to ``start``."""
    return [t - start for t in times]


def slice_samples(
    samples: Any,
    sr: int,
    start: float,
    end: float,
) -> Any:
    """Slice a mono 1-D sample array to [start, end) seconds (pure, testable)."""
    start_idx = int(max(0.0, start) * sr)
    end_idx = int(min(len(samples) / sr, end) * sr)
    return samples[start_idx:end_idx]


def slice_audio(
    wav_bytes: bytes,
    start: float,
    end: float,
    fmt: str = "wav",
) -> bytes:
    """Slice decoded audio bytes to [start, end) seconds.

    Accepts WAV/FLAC/etc. via soundfile. Returns a WAV byte string of the
    excerpt (rebased so the first sample corresponds to time 0).
    """
    import io

    import numpy as np
    import soundfile as sf

    data, sr = sf.read(io.BytesIO(wav_bytes))
    if data.ndim > 1:
        data = data.mean(axis=1)
    sliced = slice_samples(data, sr, start, end).astype(np.float32)
    out = io.BytesIO()
    sf.write(out, sliced, sr, format="WAV")
    return out.getvalue()


def slice_midi(
    midi_bytes: bytes,
    start: float,
    end: float,
) -> tuple[bytes, list[dict[str, Any]]]:
    """Slice MIDI to [start, end) and rebase note times to 0.

    Returns (midi_bytes_of_excerpt, note_dicts). The returned note dicts use
    rebased ``start``/``end`` and are suitable for transcription metrics.
    """
    import io

    import pretty_midi

    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    notes: list[dict[str, Any]] = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            if note.end <= start + _EPSILON or note.start >= end - _EPSILON:
                continue
            clipped_start = max(note.start, start) - start
            clipped_end = min(note.end, end) - start
            if clipped_end - clipped_start <= 0:
                continue
            notes.append(
                {
                    "pitch": note.pitch,
                    "start": clipped_start,
                    "end": clipped_end,
                    "velocity": note.velocity,
                }
            )

    out = pretty_midi.PrettyMIDI(initial_tempo=_first_tempo(pm))
    inst = pretty_midi.Instrument(program=0, is_drum=False)
    for n in notes:
        inst.notes.append(
            pretty_midi.Note(
                velocity=n["velocity"],
                pitch=n["pitch"],
                start=n["start"],
                end=n["end"],
            )
        )
    out.instruments.append(inst)
    buf = io.BytesIO()
    out.write(buf)
    return buf.getvalue(), notes


def slice_beat_annotations(
    beats: list[float],
    downbeats: list[float],
    start: float,
    end: float,
) -> tuple[list[float], list[float]]:
    """Filter beat/downbeat timestamps to [start, end) and rebase to 0."""
    sliced_beats = [b - start for b in beats if start - _EPSILON <= b < end - _EPSILON]
    sliced_dbs = [d - start for d in downbeats if start - _EPSILON <= d < end - _EPSILON]
    return sliced_beats, sliced_dbs


def slice_chord_annotations(
    chords: list[dict[str, Any]],
    start: float,
    end: float,
) -> list[dict[str, Any]]:
    """Filter chord annotations overlapping [start, end) and rebase times.

    Expects chord dicts with ``start`` (and optional ``end``) keys.
    """
    result: list[dict[str, Any]] = []
    for ch in chords:
        c_start = float(ch.get("start", 0))
        c_end = float(ch.get("end", c_start))
        if c_end <= start + _EPSILON or c_start >= end - _EPSILON:
            continue
        clipped = dict(ch)
        clipped["start"] = max(c_start, start) - start
        if "end" in ch:
            clipped["end"] = min(c_end, end) - start
        result.append(clipped)
    return result


def _first_tempo(pm: Any) -> float:
    try:
        _, tempos = pm.get_tempo_changes()
        if tempos is not None and len(tempos) > 0:
            return float(tempos[0])
    except Exception:
        pass
    return 120.0

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import music_features


def _semantic_notes(result: dict) -> list[tuple[int, float, float, int, float | None]]:
    return [
        (
            int(note["pitch"]),
            round(float(note["start"]), 6),
            round(float(note["end"]), 6),
            int(note["velocity"]),
            None if note.get("amplitude") is None else round(float(note["amplitude"]), 6),
        )
        for note in result["notes"]
    ]


def test_real_audio_basic_pitch_cold_then_warm_same_process() -> None:
    fixture = Path(__file__).parents[2] / "tests" / "fixtures" / "real-piano.m4a"
    source_bytes = fixture.read_bytes()
    wav_bytes = music_features.decode_audio_to_wav(source_bytes, fmt="m4a")

    # Force this acceptance probe to pay model construction on the first call.
    music_features._basic_pitch_model = None

    started = time.perf_counter()
    cold = music_features.transcribe_audio(wav_bytes, fmt="wav")
    cold_seconds = time.perf_counter() - started

    started = time.perf_counter()
    warm = music_features.transcribe_audio(wav_bytes, fmt="wav")
    warm_seconds = time.perf_counter() - started

    cold_midi_sha = hashlib.sha256(cold["midi"]).hexdigest()
    warm_midi_sha = hashlib.sha256(warm["midi"]).hexdigest()
    report = {
        "cold_seconds": round(cold_seconds, 3),
        "warm_seconds": round(warm_seconds, 3),
        "saved_seconds": round(cold_seconds - warm_seconds, 3),
        "speedup": round(cold_seconds / warm_seconds, 3) if warm_seconds else None,
        "cold_num_notes": cold["num_notes"],
        "warm_num_notes": warm["num_notes"],
        "midi_sha256_match": cold_midi_sha == warm_midi_sha,
        "semantic_notes_match": _semantic_notes(cold) == _semantic_notes(warm),
    }
    print(f"BASIC_PITCH_CACHE_BENCHMARK_JSON={json.dumps(report, sort_keys=True)}")

    assert cold["num_notes"] == warm["num_notes"]
    assert _semantic_notes(cold) == _semantic_notes(warm)
    assert cold_midi_sha == warm_midi_sha

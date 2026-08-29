from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "backend")

import music_features


def _run_once(audio: bytes):
    started = time.perf_counter()
    result = music_features.transcribe_audio(audio, fmt="m4a")
    elapsed = time.perf_counter() - started
    notes = [
        (
            int(note["pitch"]),
            round(float(note["start"]), 6),
            round(float(note["end"]), 6),
            int(note["velocity"]),
        )
        for note in result["notes"]
    ]
    return result, notes, elapsed


def main() -> None:
    fixture = Path("tests/fixtures/real-piano.m4a")
    audio = fixture.read_bytes()
    cold, cold_notes, cold_s = _run_once(audio)
    warm, warm_notes, warm_s = _run_once(audio)
    semantic_equal = cold_notes == warm_notes
    report = {
        "fixture": str(fixture),
        "fixture_sha256": hashlib.sha256(audio).hexdigest(),
        "cold_seconds": round(cold_s, 3),
        "warm_seconds": round(warm_s, 3),
        "speedup": round(cold_s / warm_s, 3) if warm_s else None,
        "seconds_saved": round(cold_s - warm_s, 3),
        "cold_num_notes": cold["num_notes"],
        "warm_num_notes": warm["num_notes"],
        "semantic_notes_equal": semantic_equal,
        "cold_midi_sha256": hashlib.sha256(cold["midi"]).hexdigest(),
        "warm_midi_sha256": hashlib.sha256(warm["midi"]).hexdigest(),
    }
    print("BASIC_PITCH_CONTROL_JSON=" + json.dumps(report, sort_keys=True))
    if not semantic_equal:
        raise SystemExit("cold/warm note semantics differ")


if __name__ == "__main__":
    main()

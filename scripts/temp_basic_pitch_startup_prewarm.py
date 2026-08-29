from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, "backend")

import music_features


def _synthetic_wav() -> bytes:
    sample_rate = 22050
    duration_s = 1.0
    t = np.arange(int(sample_rate * duration_s), dtype=np.float32) / sample_rate
    signal = (0.08 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    buffer = io.BytesIO()
    sf.write(buffer, signal, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def main() -> None:
    warmup_audio = _synthetic_wav()
    started = time.perf_counter()
    warmup_result = music_features.transcribe_audio(warmup_audio, fmt="wav")
    warmup_s = time.perf_counter() - started

    real_audio = Path("tests/fixtures/real-piano.m4a").read_bytes()
    started = time.perf_counter()
    real_result = music_features.transcribe_audio(real_audio, fmt="m4a")
    real_s = time.perf_counter() - started

    report = {
        "warmup_seconds": round(warmup_s, 3),
        "warmup_num_notes": warmup_result["num_notes"],
        "real_after_warmup_seconds": round(real_s, 3),
        "real_num_notes": real_result["num_notes"],
    }
    print("BASIC_PITCH_STARTUP_PREWARM_JSON=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

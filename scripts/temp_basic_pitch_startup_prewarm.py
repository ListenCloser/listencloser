from __future__ import annotations

import io
import json
import sys
import tempfile
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
    from basic_pitch.inference import predict

    warmup_audio = _synthetic_wav()
    with tempfile.TemporaryDirectory() as td:
        warmup_path = Path(td) / "warmup.wav"
        warmup_path.write_bytes(warmup_audio)
        started = time.perf_counter()
        _model_output, warmup_midi, warmup_events = predict(str(warmup_path))
        warmup_s = time.perf_counter() - started

    real_audio = Path("tests/fixtures/real-piano.m4a").read_bytes()
    started = time.perf_counter()
    real_result = music_features.transcribe_audio(real_audio, fmt="m4a")
    real_s = time.perf_counter() - started

    report = {
        "predict_warmup_seconds": round(warmup_s, 3),
        "warmup_event_count": len(warmup_events),
        "warmup_midi_present": warmup_midi is not None,
        "real_after_predict_warmup_seconds": round(real_s, 3),
        "real_num_notes": real_result["num_notes"],
    }
    print("BASIC_PITCH_PREDICT_PREWARM_JSON=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

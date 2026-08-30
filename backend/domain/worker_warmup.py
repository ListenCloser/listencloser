"""Worker-start warmups for expensive lazy/JIT runtime paths."""

from __future__ import annotations

import logging
import os
import tempfile
import time
import wave

import numpy as np

logger = logging.getLogger("worker_warmup")

_BASIC_PITCH_PREWARM_SAMPLE_RATE = 22050
_BASIC_PITCH_PREWARM_SECONDS = 0.5
_BASIC_PITCH_PREWARM_FREQUENCY_HZ = 440.0
_LIBROSA_PREWARM_SAMPLE_RATE = 22050
_LIBROSA_PREWARM_SECONDS = 4
_LIBROSA_PREWARM_BPM = 120


def _basic_pitch_prewarm_signal() -> np.ndarray:
    """Build a tiny deterministic tone that still executes one model window."""

    sample_count = int(_BASIC_PITCH_PREWARM_SAMPLE_RATE * _BASIC_PITCH_PREWARM_SECONDS)
    times = np.arange(sample_count, dtype=np.float32) / _BASIC_PITCH_PREWARM_SAMPLE_RATE
    signal = 0.1 * np.sin(2 * np.pi * _BASIC_PITCH_PREWARM_FREQUENCY_HZ * times)
    return signal.astype(np.float32)


def _write_basic_pitch_prewarm_wav(path: str) -> None:
    signal = _basic_pitch_prewarm_signal()
    pcm = np.clip(signal * 32767.0, -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(_BASIC_PITCH_PREWARM_SAMPLE_RATE)
        wav_file.writeframes(pcm.tobytes())


def prewarm_basic_pitch_inference() -> bool:
    """Pay Basic Pitch's process-local first-inference cost before readiness.

    Production's default transcription engine is Basic Pitch. Controlled
    same-process benchmarks show that the first prediction is much slower than
    later predictions even without retaining a global model object, so this
    warmup deliberately exercises the normal serialized-model ``predict`` path
    instead of changing model lifetime or concurrency semantics.

    Returns ``True`` when the warmup ran and ``False`` when another configured
    default transcription engine made it unnecessary. Exceptions intentionally
    propagate so the worker entrypoint can log them while continuing startup.
    """

    transcription_engine = os.environ.get("TRANSCRIPTION_ENGINE", "basic_pitch")
    if transcription_engine != "basic_pitch":
        logger.info(
            "basic_pitch_prewarm_skipped",
            extra={"transcription_engine": transcription_engine},
        )
        return False

    started = time.perf_counter()
    from basic_pitch.inference import predict

    with tempfile.TemporaryDirectory() as td:
        audio_path = os.path.join(td, "prewarm.wav")
        _write_basic_pitch_prewarm_wav(audio_path)
        _model_output, _midi_data, note_events = predict(
            audio_path,
            onset_threshold=0.5,
            frame_threshold=0.3,
        )

    duration_s = time.perf_counter() - started
    logger.info(
        "basic_pitch_prewarm_complete",
        extra={
            "duration_s": round(duration_s, 3),
            "note_count": len(note_events),
        },
    )
    return True


def _librosa_prewarm_signal() -> np.ndarray:
    """Build a tiny deterministic click train that traverses beat tracking.

    Silence is insufficient here: ``librosa.beat.beat_track`` returns early
    when its onset envelope is empty, before tempo estimation and the dynamic
    programming beat tracker execute. A short click train keeps startup work
    bounded while exercising the same non-empty branch as real music.
    """

    sample_count = _LIBROSA_PREWARM_SAMPLE_RATE * _LIBROSA_PREWARM_SECONDS
    signal = np.zeros(sample_count, dtype=np.float32)
    samples_per_beat = int(round(_LIBROSA_PREWARM_SAMPLE_RATE * 60.0 / _LIBROSA_PREWARM_BPM))
    first_click = _LIBROSA_PREWARM_SAMPLE_RATE // 4
    click_positions = np.arange(first_click, sample_count, samples_per_beat)
    signal[click_positions] = 1.0
    return signal


def prewarm_librosa_beat_tracking() -> bool:
    """Pay librosa/Numba beat-tracking cold cost before worker readiness.

    Score uses the default beat engine, which is librosa unless ``BEAT_ENGINE``
    overrides it. The first real ``librosa.beat.beat_track`` call can spend
    many seconds compiling lazy Numba kernels. Running the production call
    shape on a deterministic non-silent click train moves that one-time
    process cost out of the first user's score-generation path.

    Returns ``True`` when the warmup ran and ``False`` when another configured
    beat engine made it unnecessary. Exceptions intentionally propagate so the
    worker entrypoint can log them while continuing startup.
    """

    beat_engine = os.environ.get("BEAT_ENGINE", "librosa")
    if beat_engine != "librosa":
        logger.info("librosa_beat_prewarm_skipped", extra={"beat_engine": beat_engine})
        return False

    import librosa

    signal = _librosa_prewarm_signal()
    started = time.perf_counter()
    tempo, beats = librosa.beat.beat_track(
        y=signal,
        sr=_LIBROSA_PREWARM_SAMPLE_RATE,
        trim=False,
    )
    duration_s = time.perf_counter() - started
    beat_count = int(np.asarray(beats).size)
    if beat_count == 0:
        logger.warning(
            "librosa_beat_prewarm_no_beats",
            extra={"duration_s": round(duration_s, 3)},
        )
    logger.info(
        "librosa_beat_prewarm_complete",
        extra={
            "duration_s": round(duration_s, 3),
            "beat_count": beat_count,
            "tempo": (float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else 0.0),
        },
    )
    return True

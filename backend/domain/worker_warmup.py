"""Worker-start warmups for expensive lazy/JIT runtime paths."""

from __future__ import annotations

import logging
import os
import time

import numpy as np

logger = logging.getLogger("worker_warmup")

_LIBROSA_PREWARM_SAMPLE_RATE = 22050
_LIBROSA_PREWARM_SECONDS = 4
_LIBROSA_PREWARM_BPM = 120


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

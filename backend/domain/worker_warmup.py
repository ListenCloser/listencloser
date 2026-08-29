"""Worker-start warmups for expensive lazy/JIT runtime paths."""

from __future__ import annotations

import logging
import os
import time

import numpy as np

logger = logging.getLogger("worker_warmup")

_LIBROSA_PREWARM_SAMPLE_RATE = 22050
_LIBROSA_PREWARM_SECONDS = 1


def prewarm_librosa_beat_tracking() -> bool:
    """Pay librosa/Numba beat-tracking cold cost before worker readiness.

    Score uses the default beat engine, which is librosa unless ``BEAT_ENGINE``
    overrides it. The first ``librosa.beat.beat_track`` call can spend many
    seconds compiling lazy Numba kernels even for a tiny signal. Running the
    exact production call shape on one second of silence moves that one-time
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

    signal = np.zeros(
        _LIBROSA_PREWARM_SAMPLE_RATE * _LIBROSA_PREWARM_SECONDS,
        dtype=np.float32,
    )
    started = time.perf_counter()
    librosa.beat.beat_track(
        y=signal,
        sr=_LIBROSA_PREWARM_SAMPLE_RATE,
        trim=False,
    )
    logger.info(
        "librosa_beat_prewarm_complete",
        extra={"duration_s": round(time.perf_counter() - started, 3)},
    )
    return True

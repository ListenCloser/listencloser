from __future__ import annotations

import json
import os
import time

import librosa

from domain.worker_warmup import _librosa_prewarm_signal, prewarm_librosa_beat_tracking


def main() -> None:
    started = time.perf_counter()
    prewarm_librosa_beat_tracking()
    runtime_prewarm_s = time.perf_counter() - started

    signal = _librosa_prewarm_signal()
    started = time.perf_counter()
    _tempo, beats = librosa.beat.beat_track(y=signal, sr=22050, trim=False)
    hot_call_s = time.perf_counter() - started

    print(
        "LIBROSA_PERSISTENT_CACHE_BENCHMARK_JSON="
        + json.dumps(
            {
                "numba_cache_dir": os.environ.get("NUMBA_CACHE_DIR"),
                "runtime_prewarm_seconds": round(runtime_prewarm_s, 3),
                "hot_call_seconds": round(hot_call_s, 3),
                "beat_count": int(len(beats)),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

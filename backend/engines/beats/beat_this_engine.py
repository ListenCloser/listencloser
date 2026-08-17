"""Beat This! beat/downbeat tracking engine (experimental).

Installed optionally behind the BeatTrackingEngine interface.
Fails explicitly when beat_this is not installed; does not silently fall back.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

from engines.base import BeatTrackingEngine, BeatTrackingResult, EngineProvenance


class BeatThisEngine(BeatTrackingEngine):
    ENGINE = "beat_this"

    def __init__(self) -> None:
        pass

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_beat_this_version(),
            parameters={"device": "cpu"},
        )

    def analyze(self, wav_bytes: bytes, **kwargs: Any) -> BeatTrackingResult:
        from beat_this.inference import File2Beats  # type: ignore[import-untyped]

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                f.flush()
                tmp_path = f.name
            model = File2Beats(device="cpu")
            beats, downbeats = model(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        beats_time = [float(b) for b in beats]
        downbeats_time = [float(d) for d in downbeats]
        bpm = _bpm_from_beats(beats_time)
        return BeatTrackingResult(
            bpm=bpm,
            beats=beats_time,
            downbeats=downbeats_time if downbeats_time else None,
            beat_positions=list(range(1, len(beats_time) + 1)),
            provenance=self.provenance,
        )


def _bpm_from_beats(beats: list[float]) -> float | None:
    """Median inter-beat interval → BPM.

    Degenerate beat output yields no BPM evidence (None), never a fabricated
    default tempo: fewer than two usable beats or no positive intervals means
    the model did not produce a usable pulse.
    """
    if len(beats) < 2:
        return None
    import numpy as np

    intervals = np.diff(np.asarray(beats, dtype=float))
    intervals = intervals[intervals > 0]
    if intervals.size == 0:
        return None
    return float(60.0 / np.median(intervals))


def _beat_this_version() -> str:
    try:
        from importlib.metadata import version

        return version("beat_this")
    except Exception:
        return "unknown"

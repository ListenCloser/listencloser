"""Librosa beat tracking engine."""

from __future__ import annotations

from typing import Any

from engines.base import BeatTrackingEngine, BeatTrackingResult, EngineProvenance


class LibrosaBeatEngine(BeatTrackingEngine):
    ENGINE = "librosa"

    def __init__(self) -> None:
        pass

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_librosa_version(),
        )

    def analyze(self, wav_bytes: bytes, **kwargs: Any) -> BeatTrackingResult:
        import music_features as mf

        bpm, beats = mf.estimate_beat_grid(wav_bytes)
        return BeatTrackingResult(
            bpm=float(bpm),
            beats=beats,
            downbeats=None,
            beat_positions=None,
            provenance=self.provenance,
        )


def _librosa_version() -> str:
    try:
        import librosa

        return librosa.__version__
    except Exception:
        return "unknown"

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
        downbeats: list[float] = []
        beat_positions: list[int] = []
        if beats:
            inter_beat = [beats[i + 1] - beats[i] for i in range(len(beats) - 1)]
            if inter_beat:
                avg_interval = sum(inter_beat) / len(inter_beat)
                bar_length = avg_interval * 4
                beat_positions = list(range(len(beats)))
                downbeats = [beats[i] for i in range(0, len(beats), 4)] if bar_length > 0 else []

        return BeatTrackingResult(
            bpm=float(bpm),
            beats=beats,
            downbeats=downbeats,
            beat_positions=beat_positions,
            provenance=self.provenance,
        )


def _librosa_version() -> str:
    try:
        import librosa

        return librosa.__version__
    except Exception:
        return "unknown"

"""Current production baseline adapter using librosa."""

from __future__ import annotations

import numpy as np

from .base import PulseAdapter, PulseMetadata, PulseResult


class CurrentBaselineAdapter(PulseAdapter):
    name = "current"
    engine = "librosa"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._engine = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load current baseline: {e}") from e

    def analyze(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> PulseResult:
        if not self._loaded:
            return PulseResult(error="Engine not loaded")
        try:
            import librosa

            tempo, beat_frames = librosa.beat.beat_track(y=audio, sr=sample_rate)
            beats = librosa.frames_to_time(beat_frames, sr=sample_rate).tolist()

            return PulseResult(
                beats=beats,
                downbeats=[],
                beat_positions=[],
                tempo_bpm=float(tempo) if tempo is not None else None,
            )
        except Exception as e:
            return PulseResult(error=str(e))

    def metadata(self) -> PulseMetadata:
        return PulseMetadata(
            candidate="current",
            engine="librosa",
            code_license="ISC",
            checkpoint_license=None,
            upstream_repo="https://github.com/librosa/librosa",
            supports_beats=True,
            supports_downbeats=False,
            supports_tempo=True,
            supports_meter=False,
            supports_local_tempo=False,
            notes="Current production baseline. Spectral onset + dynamic programming.",
        )

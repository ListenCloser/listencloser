"""Current production baseline adapter using the exact hello-ai implementation.

Uses backend/music_features.estimate_beat_grid() which is the actual production path.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np

from .base import PulseAdapter, PulseMetadata, PulseResult


class CurrentBaselineAdapter(PulseAdapter):
    name = "current"
    engine = "librosa"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)

    def load(self) -> None:
        if self._loaded:
            return
        try:
            # Navigate up to backend/ directory where music_features.py lives
            backend_dir = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)

            from music_features import estimate_beat_grid

            self._estimate_beat_grid = estimate_beat_grid
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
            import soundfile as sf

            buf = io.BytesIO()
            sf.write(buf, audio, sample_rate, format="WAV")
            wav_bytes = buf.getvalue()

            bpm, beats = self._estimate_beat_grid(wav_bytes)

            return PulseResult(
                beats=beats,
                downbeats=[],
                beat_positions=[],
                tempo_bpm=bpm,
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
            notes=(
                "Current production baseline. "
                "Uses backend/music_features.estimate_beat_grid() "
                "which calls librosa.beat.beat_track with trim=False."
            ),
        )

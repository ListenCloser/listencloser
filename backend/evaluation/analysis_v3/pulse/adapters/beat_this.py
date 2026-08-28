"""Beat This adapter."""

from __future__ import annotations

import numpy as np

from .base import PulseAdapter, PulseMetadata, PulseResult


class BeatThisAdapter(PulseAdapter):
    name = "beat_this"
    engine = "beat_this"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from beat_this.inference import File2Beats

            self._model = File2Beats(device=self.device)
            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load Beat This: {e}") from e

    def analyze(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> PulseResult:
        if not self._loaded:
            return PulseResult(error="Model not loaded")
        try:
            import os
            import tempfile

            import soundfile as sf

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f, audio, sample_rate, format="WAV")
                tmp_path = f.name

            try:
                beats, downbeats = self._model(tmp_path)
            finally:
                os.unlink(tmp_path)

            beats_time = [float(b) for b in beats]
            downbeats_time = [float(d) for d in downbeats]

            bpm = None
            if len(beats_time) >= 2:
                import numpy as np

                intervals = np.diff(np.asarray(beats_time))
                intervals = intervals[intervals > 0]
                if intervals.size > 0:
                    bpm = float(60.0 / np.median(intervals))

            return PulseResult(
                beats=beats_time,
                downbeats=downbeats_time,
                beat_positions=list(range(1, len(beats_time) + 1)),
                tempo_bpm=bpm,
            )
        except Exception as e:
            return PulseResult(error=str(e))

    def metadata(self) -> PulseMetadata:
        return PulseMetadata(
            candidate="beat_this",
            engine="beat_this",
            code_license="MIT",
            checkpoint_license="MIT",
            upstream_repo="https://github.com/inria-ml/beat_this",
            supports_beats=True,
            supports_downbeats=True,
            supports_tempo=True,
            supports_meter=False,
            supports_local_tempo=False,
            notes="CNN-based beat/downbeat tracker from INRIA.",
        )

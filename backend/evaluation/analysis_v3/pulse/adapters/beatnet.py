"""BeatNet adapter."""

from __future__ import annotations

import numpy as np

from .base import PulseAdapter, PulseMetadata, PulseResult


class BeatNetAdapter(PulseAdapter):
    name = "beatnet"
    engine = "beatnet"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from BeatNet.BeatNet import BeatNet

            self._model = BeatNet(1, mode="online", device=self.device)
            self._loaded = True
        except Exception as e:
            raise RuntimeError(
                f"Failed to load BeatNet: {e}. "
                "BeatNet requires madmom which has numpy compatibility issues "
                "with numpy>=1.24. Marked as REVISIT."
            ) from e

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
                output = self._model.process(tmp_path)
            finally:
                os.unlink(tmp_path)

            if output is None or len(output) == 0:
                return PulseResult(error="No output from BeatNet")

            beats = []
            downbeats = []
            beat_positions = []

            for item in output:
                if len(item) >= 2:
                    time_val = float(item[0])
                    beat_type = int(item[1])
                    if beat_type == 1:
                        beats.append(time_val)
                        downbeats.append(time_val)
                        beat_positions.append(1)
                    else:
                        beats.append(time_val)
                        beat_positions.append(beat_type)

            bpm = None
            if len(beats) >= 2:
                intervals = np.diff(np.asarray(beats))
                intervals = intervals[intervals > 0]
                if intervals.size > 0:
                    bpm = float(60.0 / np.median(intervals))

            return PulseResult(
                beats=beats,
                downbeats=downbeats,
                beat_positions=beat_positions,
                tempo_bpm=bpm,
            )
        except Exception as e:
            return PulseResult(error=str(e))

    def metadata(self) -> PulseMetadata:
        return PulseMetadata(
            candidate="beatnet",
            engine="beatnet",
            code_license="MIT",
            checkpoint_license="MIT",
            upstream_repo="https://github.com/mjhyman/BeatNet",
            supports_beats=True,
            supports_downbeats=True,
            supports_tempo=True,
            supports_meter=True,
            supports_local_tempo=True,
            notes="Joint beat/downbeat/tempo/meter tracker.",
        )

"""Beat This adapter."""

from __future__ import annotations

import numpy as np

from .base import PulseAdapter, PulseMetadata, PulseResult


class BeatThisAdapter(PulseAdapter):
    name = "beat_this"
    engine = "beat_this"

    def __init__(self, device: str = "cpu", checkpoint_name: str = "final0"):
        super().__init__(device)
        self.checkpoint_name = checkpoint_name
        self._model = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from beat_this.inference import File2Beats

            self._model = File2Beats(
                checkpoint_path=self.checkpoint_name,
                device=self.device,
            )
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
        training_datasets: tuple[str, ...] = ()
        held_out_datasets: tuple[str, ...] = ()
        if self.checkpoint_name.startswith(("final", "small")):
            training_datasets = (
                "simac",
                "smc",
                "hainsworth",
                "ballroom",
                "hjdb",
                "beatles",
                "harmonix",
                "rwc",
                "tapcorrect",
                "jaah",
                "filosax",
                "asap",
                "groove_midi",
                "guitarset",
                "candombe",
            )
            held_out_datasets = ("gtzan",)

        return PulseMetadata(
            candidate="beat_this",
            engine="beat_this",
            code_license="MIT",
            checkpoint_license="MIT",
            upstream_repo="https://github.com/CPJKU/beat_this",
            checkpoint_name=self.checkpoint_name,
            training_datasets=training_datasets,
            held_out_datasets=held_out_datasets,
            supports_beats=True,
            supports_downbeats=True,
            supports_tempo=True,
            supports_meter=False,
            supports_local_tempo=False,
            notes=(
                "Beat/downbeat tracker from CPJKU. The default final0 checkpoint "
                "was trained on the published multi-dataset training collection "
                "excluding GTZAN. Tempo is derived from median inter-beat interval, "
                "not an independently predicted tempo output."
            ),
        )

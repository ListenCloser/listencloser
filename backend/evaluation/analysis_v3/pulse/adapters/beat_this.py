"""Beat This adapter."""

from __future__ import annotations

import numpy as np

from .base import PulseAdapter, PulseMetadata, PulseResult

_BEAT_THIS_TRAINING_DATASETS = (
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
_SPLIT_SOURCE = "https://github.com/CPJKU/beat_this_annotations"
_SPLIT_VERSION = "v1.0"


def _single_partition_ids(partition: str) -> tuple[str, ...]:
    return tuple(f"{dataset}_single_split_{partition}" for dataset in _BEAT_THIS_TRAINING_DATASETS)


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
        training_partition = None
        held_out_partition = None
        split_source = None
        split_version = None
        notes = "Beat/downbeat tracker from CPJKU. "

        if self.checkpoint_name.startswith(("final", "small")):
            training_datasets = _BEAT_THIS_TRAINING_DATASETS
            held_out_datasets = ("gtzan",)
            notes += (
                "The final*/small* checkpoints were trained on the published multi-dataset "
                "collection excluding GTZAN. "
            )
        elif self.checkpoint_name.startswith("single_"):
            training_datasets = _BEAT_THIS_TRAINING_DATASETS + _single_partition_ids("train")
            held_out_datasets = _single_partition_ids("val")
            training_partition = "single_split_train"
            held_out_partition = "single_split_val"
            split_source = _SPLIT_SOURCE
            split_version = _SPLIT_VERSION
            notes += (
                "The single_* checkpoints use Beat This annotations v1.0 single.split. "
                "Unpartitioned dataset identifiers remain marked as training-overlap so the "
                "generic guard fails closed; only explicit *_single_split_val manifests are "
                "recognized as held out. "
            )

        notes += (
            "Tempo is derived from median inter-beat interval, not an independently "
            "predicted tempo output."
        )
        return PulseMetadata(
            candidate=self.name,
            engine="beat_this",
            code_license="MIT",
            checkpoint_license="MIT",
            upstream_repo="https://github.com/CPJKU/beat_this",
            checkpoint_name=self.checkpoint_name,
            training_datasets=training_datasets,
            held_out_datasets=held_out_datasets,
            training_partition=training_partition,
            held_out_partition=held_out_partition,
            split_source=split_source,
            split_version=split_version,
            supports_beats=True,
            supports_downbeats=True,
            supports_tempo=True,
            supports_meter=False,
            supports_local_tempo=False,
            notes=notes,
        )


class BeatThisSingleFinal0Adapter(BeatThisAdapter):
    """Beat This single-split seed-0 checkpoint for held-out validation evaluation."""

    name = "beat_this_single_final0"

    def __init__(self, device: str = "cpu"):
        super().__init__(device=device, checkpoint_name="single_final0")

"""Measure whether a separated drum stem improves the production beat grid.

This is the first current-main replay of historical PR #426. It intentionally
contains only the separation -> beat/downbeat downstream question and reuses the
canonical pulse metrics already merged under Analysis V3.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import numpy as np
import soundfile as sf
from backend.evaluation.analysis_v3.pulse.metrics import compute_beat_f1, compute_event_timing


@dataclass(frozen=True)
class BeatDownstreamScore:
    f1: float
    precision: float
    recall: float
    reference_coverage: float
    predicted_coverage: float
    absolute_median_error_seconds: float | None
    absolute_p95_error_seconds: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "f1": round(self.f1, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "reference_coverage": round(self.reference_coverage, 4),
            "predicted_coverage": round(self.predicted_coverage, 4),
            "absolute_median_error_seconds": self.absolute_median_error_seconds,
            "absolute_p95_error_seconds": self.absolute_p95_error_seconds,
        }


@dataclass(frozen=True)
class BeatDownstreamComparison:
    mixture: BeatDownstreamScore
    drums: BeatDownstreamScore

    @property
    def f1_delta(self) -> float:
        return self.drums.f1 - self.mixture.f1

    @property
    def reference_coverage_delta(self) -> float:
        return self.drums.reference_coverage - self.mixture.reference_coverage

    def to_dict(self) -> dict[str, Any]:
        return {
            "mixture": self.mixture.to_dict(),
            "drums": self.drums.to_dict(),
            "f1_delta": round(self.f1_delta, 4),
            "reference_coverage_delta": round(self.reference_coverage_delta, 4),
        }


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim == 2:
        if samples.shape[0] <= 8 and samples.shape[0] < samples.shape[1]:
            samples = samples.T
        elif samples.shape[1] > 8:
            raise ValueError(f"Unsupported audio shape: {samples.shape}")
    elif samples.ndim != 1:
        raise ValueError(f"Unsupported audio rank: {samples.ndim}")

    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV", subtype="FLOAT")
    return buffer.getvalue()


def _score_estimated_beats(predicted: list[float], reference: list[float]) -> BeatDownstreamScore:
    beat = compute_beat_f1(predicted, reference, tolerance=0.07)
    timing = compute_event_timing(predicted, reference, tolerance=0.07).to_dict()
    return BeatDownstreamScore(
        f1=beat.f1,
        precision=beat.precision,
        recall=beat.recall,
        reference_coverage=float(timing["reference_coverage"]),
        predicted_coverage=float(timing["predicted_coverage"]),
        absolute_median_error_seconds=timing["absolute_median_seconds"],
        absolute_p95_error_seconds=timing["absolute_p95_seconds"],
    )


def score_production_beat_grid(
    audio: np.ndarray,
    sample_rate: int,
    reference_beats: list[float],
) -> BeatDownstreamScore:
    """Score the exact production beat estimator with current pulse metrics."""
    if not reference_beats:
        raise ValueError("reference_beats must be non-empty")

    from music_features import estimate_beat_grid

    _, predicted_beats = estimate_beat_grid(_audio_to_wav_bytes(audio, sample_rate))
    return _score_estimated_beats([float(value) for value in predicted_beats], reference_beats)


def compare_mixture_vs_drums(
    mixture_audio: np.ndarray,
    drums_audio: np.ndarray,
    sample_rate: int,
    reference_beats: list[float],
) -> BeatDownstreamComparison:
    """Compare production beat evidence before and after drum separation."""
    return BeatDownstreamComparison(
        mixture=score_production_beat_grid(mixture_audio, sample_rate, reference_beats),
        drums=score_production_beat_grid(drums_audio, sample_rate, reference_beats),
    )

"""Evaluation-only structural-boundary baseline built from librosa primitives.

This is deliberately not a product engine.  It produces *unlabelled candidate
boundaries* from CENS chroma, a self-similarity recurrence matrix, and novelty
peak-picking.  Its purpose is to make a cheap, reproducible baseline available
for a future benchmark; it must not be turned into a section-label claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np


@dataclass(frozen=True)
class BoundaryProposal:
    """One unlabelled candidate transition with seconds-based evidence."""

    time_seconds: float
    novelty: float


@dataclass(frozen=True)
class StructureBaselineResult:
    """Diagnostic output; recurrence is retained only as compact statistics."""

    duration_seconds: float
    proposals: tuple[BoundaryProposal, ...]
    frame_count: int
    recurrence_density: float
    parameters: dict[str, int | float]


def _normalise(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return values
    maximum = float(np.max(values))
    return values / maximum if maximum > 0 else np.zeros_like(values)


def chroma_novelty(chroma: np.ndarray, *, comparison_frames: int = 8) -> np.ndarray:
    """Return a bounded change curve from an already-computed chroma matrix.

    Comparing symmetric chroma windows makes a change peak independent of an
    arbitrary absolute key.  The first/last comparison window is intentionally
    zero because a recording boundary is not a structural transition.
    """
    if chroma.ndim != 2:
        raise ValueError("chroma must have shape (features, frames)")
    if comparison_frames < 1:
        raise ValueError("comparison_frames must be positive")
    novelty = np.zeros(chroma.shape[1], dtype=float)
    if chroma.shape[1] <= comparison_frames * 2:
        return novelty
    left = chroma[:, : -comparison_frames * 2]
    right = chroma[:, comparison_frames * 2 :]
    novelty[comparison_frames:-comparison_frames] = np.linalg.norm(right - left, axis=0)
    return _normalise(novelty)


def pick_boundary_frames(
    novelty: np.ndarray,
    *,
    hop_length: int,
    sample_rate: int,
    min_separation_seconds: float = 4.0,
    prominence: float = 0.2,
) -> np.ndarray:
    """Peak-pick unlabelled candidates, excluding the recording endpoints."""
    if hop_length <= 0 or sample_rate <= 0:
        raise ValueError("hop_length and sample_rate must be positive")
    if not 0 <= prominence <= 1:
        raise ValueError("prominence must be between zero and one")
    wait = max(1, round(min_separation_seconds * sample_rate / hop_length))
    peaks = librosa.util.peak_pick(
        _normalise(novelty),
        pre_max=wait,
        post_max=wait,
        pre_avg=wait,
        post_avg=wait,
        delta=prominence,
        wait=wait,
    )
    return peaks[(peaks > 0) & (peaks < len(novelty) - 1)]


def propose_boundaries(
    audio: np.ndarray,
    sample_rate: int,
    *,
    hop_length: int = 512,
    comparison_frames: int = 8,
    min_separation_seconds: float = 4.0,
    prominence: float = 0.2,
) -> StructureBaselineResult:
    """Produce candidate boundaries using maintained librosa MIR primitives."""
    if audio.size == 0:
        raise ValueError("audio must not be empty")
    # CENS uses a 2,048-sample analysis frame.  A shorter clip cannot provide
    # enough temporal context for a recurrence relation, so withholding rather
    # than producing a plausible-looking boundary is the truthful result.
    if len(audio) < 2_048:
        return StructureBaselineResult(
            duration_seconds=round(float(len(audio) / sample_rate), 3),
            proposals=(),
            frame_count=0,
            recurrence_density=0.0,
            parameters={
                "hop_length": hop_length,
                "comparison_frames": comparison_frames,
                "min_separation_seconds": min_separation_seconds,
                "prominence": prominence,
            },
        )
    chroma = librosa.feature.chroma_cens(y=audio, sr=sample_rate, hop_length=hop_length)
    if chroma.shape[1] < 4:
        return StructureBaselineResult(
            duration_seconds=round(float(len(audio) / sample_rate), 3),
            proposals=(),
            frame_count=int(chroma.shape[1]),
            recurrence_density=0.0,
            parameters={
                "hop_length": hop_length,
                "comparison_frames": comparison_frames,
                "min_separation_seconds": min_separation_seconds,
                "prominence": prominence,
            },
        )
    # The recurrence matrix is a standard structure-analysis primitive.  It is
    # intentionally used only to report diagnostic density, not to invent labels.
    recurrence = librosa.segment.recurrence_matrix(chroma, metric="cosine", sym=True)
    novelty = chroma_novelty(chroma, comparison_frames=comparison_frames)
    frames = pick_boundary_frames(
        novelty,
        hop_length=hop_length,
        sample_rate=sample_rate,
        min_separation_seconds=min_separation_seconds,
        prominence=prominence,
    )
    times = librosa.frames_to_time(frames, sr=sample_rate, hop_length=hop_length)
    return StructureBaselineResult(
        duration_seconds=round(float(len(audio) / sample_rate), 3),
        proposals=tuple(
            BoundaryProposal(
                time_seconds=round(float(time), 3), novelty=round(float(novelty[frame]), 4)
            )
            for frame, time in zip(frames, times, strict=True)
        ),
        frame_count=int(chroma.shape[1]),
        recurrence_density=round(float(np.count_nonzero(recurrence)) / recurrence.size, 5),
        parameters={
            "hop_length": hop_length,
            "comparison_frames": comparison_frames,
            "min_separation_seconds": min_separation_seconds,
            "prominence": prominence,
        },
    )


def propose_file(path: str | Path, **kwargs: int | float) -> StructureBaselineResult:
    """Decode an audio file and run the evaluation-only baseline."""
    audio, sample_rate = librosa.load(path, sr=None, mono=True)
    return propose_boundaries(audio, sample_rate, **kwargs)

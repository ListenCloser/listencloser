"""Transparent experimental within-recording structure candidates.

This is deliberately a small control built from the maintained NumPy/SciPy/
librosa stack. It finds candidate boundaries from recurrence-matrix novelty and
then groups segment descriptors for inspectable A/B/A?-style navigation.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from uuid import UUID

import librosa
import numpy as np
from scipy.signal import find_peaks

from domain.structure_map_report import (
    METHOD_ID,
    StructureCandidateSpan,
    StructureMapMethod,
    StructureMapReport,
)
from perceptual_evidence import CANONICAL_SAMPLE_RATE, canonicalize_audio_bytes

DEFAULT_HOP_LENGTH = 4096
DEFAULT_MIN_SPAN_SECONDS = 8.0
DEFAULT_NOVELTY_SECONDS = 6.0
DEFAULT_REPEAT_SIMILARITY = 0.82
MAX_SPANS = 12


def _package_version(name: str, fallback: str = "unknown") -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return fallback


def _feature_stack(audio: np.ndarray, sample_rate: int, hop_length: int) -> np.ndarray:
    chroma = librosa.feature.chroma_stft(y=audio, sr=sample_rate, hop_length=hop_length)
    mfcc = librosa.feature.mfcc(
        y=audio,
        sr=sample_rate,
        n_mfcc=8,
        hop_length=hop_length,
    )
    rms = librosa.feature.rms(y=audio, hop_length=hop_length)
    feature = np.vstack([chroma, mfcc, rms])
    feature -= np.mean(feature, axis=1, keepdims=True)
    scale = np.std(feature, axis=1, keepdims=True)
    feature /= np.where(scale > 1e-8, scale, 1.0)
    return feature.astype(np.float32, copy=False)


def _checkerboard_kernel(radius: int) -> np.ndarray:
    radius = max(2, int(radius))
    coordinates = np.arange(-radius, radius, dtype=float)
    xx, yy = np.meshgrid(coordinates, coordinates, indexing="ij")
    sigma = max(radius / 2.0, 1.0)
    gaussian = np.exp(-(xx * xx + yy * yy) / (2.0 * sigma * sigma))
    checker = np.sign(xx * yy)
    checker[checker == 0] = 1.0
    kernel = gaussian * checker
    kernel -= kernel.mean()
    norm = np.sum(np.abs(kernel))
    return kernel / norm if norm > 0 else kernel


def _novelty_curve(recurrence: np.ndarray, radius: int) -> np.ndarray:
    kernel = _checkerboard_kernel(radius)
    size = recurrence.shape[0]
    novelty = np.zeros(size, dtype=float)
    half = kernel.shape[0] // 2
    for index in range(half, size - half):
        patch = recurrence[index - half : index + half, index - half : index + half]
        novelty[index] = float(np.sum(patch * kernel))
    novelty = np.maximum(novelty, 0.0)
    peak = float(np.max(novelty)) if novelty.size else 0.0
    return novelty / peak if peak > 0 else novelty


def _candidate_boundaries(
    recurrence: np.ndarray,
    *,
    duration_seconds: float,
    frame_seconds: float,
    novelty_seconds: float,
    min_span_seconds: float,
) -> list[int]:
    frame_count = recurrence.shape[0]
    if frame_count < 4:
        return [0, frame_count]
    radius = max(2, round(novelty_seconds / frame_seconds))
    novelty = _novelty_curve(recurrence, radius)
    min_distance = max(1, round(min_span_seconds / frame_seconds))
    positive = novelty[novelty > 0]
    prominence = max(0.08, float(np.median(positive)) if positive.size else 0.08)
    peaks, properties = find_peaks(
        novelty,
        distance=min_distance,
        prominence=prominence,
    )
    ranked = sorted(
        zip(
            peaks.tolist(),
            properties.get("prominences", np.zeros(len(peaks))).tolist(),
            strict=False,
        ),
        key=lambda item: item[1],
        reverse=True,
    )[: max(0, MAX_SPANS - 1)]
    boundaries = [0, *sorted(index for index, _ in ranked), frame_count]

    # Remove tiny edge/interior spans deterministically after peak ranking.
    compact = [boundaries[0]]
    for boundary in boundaries[1:-1]:
        if (boundary - compact[-1]) * frame_seconds >= min_span_seconds:
            compact.append(boundary)
    if (frame_count - compact[-1]) * frame_seconds < min_span_seconds and len(compact) > 1:
        compact.pop()
    compact.append(frame_count)
    if len(compact) == 2 and duration_seconds >= 2 * min_span_seconds:
        # A completely flat novelty curve is more honest as one span than an
        # invented midpoint. Keep this branch explicit for readability.
        return compact
    return compact


def _segment_descriptor(feature: np.ndarray, start: int, end: int) -> np.ndarray:
    if end <= start:
        return np.zeros(feature.shape[0], dtype=float)
    descriptor = np.median(feature[:, start:end], axis=1).astype(float)
    norm = float(np.linalg.norm(descriptor))
    return descriptor / norm if norm > 1e-8 else descriptor


def _label_segments(
    feature: np.ndarray,
    boundaries: list[int],
    repeat_similarity: float,
) -> list[tuple[str, str | None, float | None]]:
    prototypes: list[tuple[str, np.ndarray]] = []
    labels: list[tuple[str, str | None, float | None]] = []
    for start, end in zip(boundaries[:-1], boundaries[1:], strict=False):
        descriptor = _segment_descriptor(feature, start, end)
        best_label: str | None = None
        best_similarity = -1.0
        for label, prototype in prototypes:
            similarity = float(np.dot(descriptor, prototype))
            if similarity > best_similarity:
                best_label, best_similarity = label, similarity
        if best_label is not None and best_similarity >= repeat_similarity:
            labels.append((f"{best_label}?", best_label, round(best_similarity, 3)))
            continue
        label = chr(ord("A") + min(len(prototypes), 25))
        prototypes.append((label, descriptor))
        labels.append((label, None, None))
    return labels


def build_structure_map(
    audio: np.ndarray,
    *,
    source_version_id: UUID,
    sample_rate: int = CANONICAL_SAMPLE_RATE,
    hop_length: int = DEFAULT_HOP_LENGTH,
    novelty_seconds: float = DEFAULT_NOVELTY_SECONDS,
    min_span_seconds: float = DEFAULT_MIN_SPAN_SECONDS,
    repeat_similarity: float = DEFAULT_REPEAT_SIMILARITY,
) -> StructureMapReport:
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim != 1 or samples.size == 0:
        raise ValueError("structure_map requires non-empty mono audio")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    duration = float(samples.size / sample_rate)
    feature = _feature_stack(samples, sample_rate, hop_length)
    if feature.shape[1] < 4:
        raise ValueError("audio is too short for recurrence analysis")

    width = max(1, round(2.0 * sample_rate / hop_length))
    recurrence = librosa.segment.recurrence_matrix(
        feature,
        mode="affinity",
        metric="cosine",
        sym=True,
        width=min(width, max(1, feature.shape[1] // 3)),
    ).astype(float)
    frame_seconds = hop_length / sample_rate
    boundaries = _candidate_boundaries(
        recurrence,
        duration_seconds=duration,
        frame_seconds=frame_seconds,
        novelty_seconds=novelty_seconds,
        min_span_seconds=min_span_seconds,
    )
    labels = _label_segments(feature, boundaries, repeat_similarity)
    spans: list[StructureCandidateSpan] = []
    for (start, end), (label, recurrence_of, similarity) in zip(
        zip(boundaries[:-1], boundaries[1:], strict=False),
        labels,
        strict=False,
    ):
        spans.append(
            StructureCandidateSpan(
                label=label,
                start_seconds=round(min(duration, start * frame_seconds), 3),
                end_seconds=round(min(duration, end * frame_seconds), 3),
                recurrence_of=recurrence_of,
                similarity=similarity,
            )
        )
    if spans:
        spans[-1] = spans[-1].model_copy(update={"end_seconds": round(duration, 3)})

    return StructureMapReport(
        source_version_id=source_version_id,
        duration_seconds=round(duration, 3),
        method=StructureMapMethod(
            librosa_version=_package_version(
                "librosa",
                str(getattr(librosa, "__version__", "unknown")),
            ),
            scipy_version=_package_version("scipy"),
            parameters={
                "sample_rate": sample_rate,
                "hop_length": hop_length,
                "novelty_seconds": novelty_seconds,
                "min_span_seconds": min_span_seconds,
                "repeat_similarity": repeat_similarity,
                "max_spans": MAX_SPANS,
            },
        ),
        candidate_spans=spans,
    )


def extract_structure_map_from_bytes(
    audio_bytes: bytes,
    *,
    source_version_id: UUID,
    fmt: str,
) -> StructureMapReport:
    samples = canonicalize_audio_bytes(audio_bytes, fmt=fmt)
    return build_structure_map(samples, source_version_id=source_version_id)


__all__ = [
    "METHOD_ID",
    "build_structure_map",
    "extract_structure_map_from_bytes",
]

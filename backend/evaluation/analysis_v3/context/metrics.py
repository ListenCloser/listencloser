"""Deterministic metrics for multi-label context and segment-stability probes.

These helpers deliberately operate on raw model scores. A similarity or sigmoid
output is not called a calibrated confidence unless a separate calibration step
has actually been performed.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def _validate_matrices(y_true: np.ndarray, y_score: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    truth = np.asarray(y_true, dtype=bool)
    scores = np.asarray(y_score, dtype=float)
    if truth.ndim != 2 or scores.ndim != 2:
        raise ValueError("y_true and y_score must be 2-D matrices")
    if truth.shape != scores.shape:
        raise ValueError("y_true and y_score must have the same shape")
    if truth.shape[1] == 0:
        raise ValueError("at least one label is required")
    if not np.isfinite(scores).all():
        raise ValueError("y_score must contain only finite values")
    return truth, scores


def _validate_k(k: int, n_labels: int) -> None:
    if k < 1 or k > n_labels:
        raise ValueError(f"k must be in [1, {n_labels}]")


def precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    """Mean sample-wise precision@k for a multi-label task."""
    truth, scores = _validate_matrices(y_true, y_score)
    _validate_k(k, truth.shape[1])
    order = np.argsort(-scores, axis=1, kind="stable")[:, :k]
    hits = np.take_along_axis(truth, order, axis=1).sum(axis=1)
    return float(np.mean(hits / k))


def recall_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    """Mean sample-wise recall@k, excluding rows with no positive labels."""
    truth, scores = _validate_matrices(y_true, y_score)
    _validate_k(k, truth.shape[1])
    positives = truth.sum(axis=1)
    valid = positives > 0
    if not np.any(valid):
        raise ValueError("recall@k requires at least one sample with a positive label")
    order = np.argsort(-scores, axis=1, kind="stable")[:, :k]
    hits = np.take_along_axis(truth, order, axis=1).sum(axis=1)
    return float(np.mean(hits[valid] / positives[valid]))


def label_ranking_average_precision(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Sample-wise label-ranking average precision without sklearn.

    For each positive label, this computes precision at the rank where that
    label appears, then averages over positives and finally over non-empty
    samples. Ties are deterministic because stable sorting preserves label order.
    """
    truth, scores = _validate_matrices(y_true, y_score)
    sample_scores: list[float] = []
    for sample_truth, sample_score in zip(truth, scores, strict=True):
        positives = int(sample_truth.sum())
        if positives == 0:
            continue
        order = np.argsort(-sample_score, kind="stable")
        ranked_truth = sample_truth[order]
        cumulative = np.cumsum(ranked_truth)
        positive_ranks = np.flatnonzero(ranked_truth) + 1
        precisions = cumulative[positive_ranks - 1] / positive_ranks
        sample_scores.append(float(np.mean(precisions)))
    if not sample_scores:
        raise ValueError("average precision requires at least one positive label")
    return float(np.mean(sample_scores))


def _top_k_set(scores: np.ndarray, k: int) -> set[int]:
    order = np.argsort(-scores, kind="stable")[:k]
    return {int(index) for index in order}


def top_k_jaccard(score_rows: np.ndarray, k: int) -> float:
    """Mean adjacent-window Jaccard similarity of top-k label sets.

    This is a stability diagnostic, not an accuracy metric. A trivially constant
    model can score perfectly, so it must always be interpreted alongside label
    accuracy/utility evidence.
    """
    rows = np.asarray(score_rows, dtype=float)
    if rows.ndim != 2:
        raise ValueError("score_rows must be a 2-D matrix")
    _validate_k(k, rows.shape[1])
    if len(rows) < 2:
        return 1.0
    if not np.isfinite(rows).all():
        raise ValueError("score_rows must contain only finite values")
    similarities: list[float] = []
    previous = _top_k_set(rows[0], k)
    for row in rows[1:]:
        current = _top_k_set(row, k)
        union = previous | current
        similarities.append(len(previous & current) / len(union))
        previous = current
    return float(np.mean(similarities))


def rank_zero_shot(
    audio_embedding: np.ndarray,
    label_embeddings: np.ndarray,
    labels: Sequence[str],
) -> list[tuple[str, float]]:
    """Rank labels by cosine similarity to one audio embedding."""
    audio = np.asarray(audio_embedding, dtype=float).reshape(-1)
    text = np.asarray(label_embeddings, dtype=float)
    if text.ndim != 2:
        raise ValueError("label_embeddings must be a 2-D matrix")
    if text.shape[0] != len(labels):
        raise ValueError("labels must match the number of label embeddings")
    if text.shape[1] != audio.shape[0]:
        raise ValueError("audio and text embedding dimensions must match")
    if not np.isfinite(audio).all() or not np.isfinite(text).all():
        raise ValueError("embeddings must contain only finite values")

    audio_norm = np.linalg.norm(audio)
    text_norms = np.linalg.norm(text, axis=1)
    if audio_norm == 0 or np.any(text_norms == 0):
        raise ValueError("zero vectors cannot be cosine-normalized")
    scores = (text @ audio) / (text_norms * audio_norm)
    order = np.argsort(-scores, kind="stable")
    return [(str(labels[index]), float(scores[index])) for index in order]

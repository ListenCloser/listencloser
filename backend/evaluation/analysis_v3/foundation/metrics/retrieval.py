"""Retrieval metrics for foundation model evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class RetrievalResult:
    query_id: str
    retrieved_ids: list[str]
    ranks: dict[str, int] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    recall_at_1: float | None = None
    recall_at_5: float | None = None
    mrr: float | None = None
    notes: str = ""


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def compute_similarity_matrix(embeddings: dict[str, np.ndarray]) -> np.ndarray:
    ids = sorted(embeddings.keys())
    n = len(ids)
    matrix = np.zeros((n, n))
    for i, id_a in enumerate(ids):
        for j, id_b in enumerate(ids):
            if i <= j:
                sim = cosine_similarity(embeddings[id_a], embeddings[id_b])
                matrix[i, j] = sim
                matrix[j, i] = sim
    return matrix


def retrieve_nearest_neighbors(
    query_id: str,
    embeddings: dict[str, np.ndarray],
    exclude_ids: set[str] | None = None,
    top_k: int = 10,
) -> list[tuple[str, float]]:
    if query_id not in embeddings:
        return []
    query_emb = embeddings[query_id]
    exclude = exclude_ids or set()
    exclude.add(query_id)

    similarities: list[tuple[str, float]] = []
    for other_id, other_emb in embeddings.items():
        if other_id in exclude:
            continue
        sim = cosine_similarity(query_emb, other_emb)
        similarities.append((other_id, sim))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]


def compute_recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for rid in top_k if rid in relevant_ids)
    return hits / min(k, len(relevant_ids))


def compute_mrr(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    if not relevant_ids:
        return 0.0
    for i, rid in enumerate(retrieved_ids):
        if rid in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def evaluate_retrieval(
    query_id: str,
    embeddings: dict[str, np.ndarray],
    relevant_ids: set[str],
    exclude_ids: set[str] | None = None,
    top_k: int = 10,
) -> RetrievalResult:
    neighbors = retrieve_nearest_neighbors(
        query_id, embeddings, exclude_ids=exclude_ids, top_k=top_k
    )
    retrieved_ids = [nid for nid, _ in neighbors]
    scores = {nid: score for nid, score in neighbors}
    ranks = {nid: i + 1 for i, nid in enumerate(retrieved_ids)}

    return RetrievalResult(
        query_id=query_id,
        retrieved_ids=retrieved_ids,
        ranks=ranks,
        scores=scores,
        recall_at_1=compute_recall_at_k(retrieved_ids, relevant_ids, 1),
        recall_at_5=compute_recall_at_k(retrieved_ids, relevant_ids, 5),
        mrr=compute_mrr(retrieved_ids, relevant_ids),
    )


def evaluate_cross_representation(
    audio_embeddings: dict[str, np.ndarray],
    symbolic_embeddings: dict[str, np.ndarray],
    matched_pairs: list[tuple[str, str]],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for audio_id, symbolic_id in matched_pairs:
        if audio_id not in audio_embeddings or symbolic_id not in symbolic_embeddings:
            results.append({
                "audio_id": audio_id,
                "symbolic_id": symbolic_id,
                "rank": None,
                "error": "missing embedding",
            })
            continue

        audio_emb = audio_embeddings[audio_id]
        symbolic_emb = symbolic_embeddings[symbolic_id]

        similarities: list[tuple[str, float]] = []
        for other_id, other_emb in symbolic_embeddings.items():
            sim = cosine_similarity(audio_emb, other_emb)
            similarities.append((other_id, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)

        rank = None
        for i, (sid, _) in enumerate(similarities):
            if sid == symbolic_id:
                rank = i + 1
                break

        results.append({
            "audio_id": audio_id,
            "symbolic_id": symbolic_id,
            "rank": rank,
            "total_candidates": len(similarities),
            "matched_score": cosine_similarity(audio_emb, symbolic_emb),
        })

    ranks = [r["rank"] for r in results if r.get("rank") is not None]
    return {
        "per_pair": results,
        "mean_rank": float(np.mean(ranks)) if ranks else None,
        "median_rank": float(np.median(ranks)) if ranks else None,
        "mrr": float(np.mean([1.0 / r for r in ranks])) if ranks else None,
        "recall_at_1": float(np.mean([1.0 if r <= 1 else 0.0 for r in ranks])) if ranks else None,
        "recall_at_5": float(np.mean([1.0 if r <= 5 else 0.0 for r in ranks])) if ranks else None,
    }

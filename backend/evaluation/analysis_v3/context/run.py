"""Analysis V3 context/style/instrument evaluation runner.

Required-CI-safe usage (no model download):
  python -m backend.evaluation.analysis_v3.context.run --task prior

Opt-in local probe (requires cached audio and CLAP checkpoint access):
  python -m backend.evaluation.analysis_v3.context.run --task zero-shot --device cpu
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from ..foundation.adapters.clap import CLAPAdapter
from .metrics import (
    label_ranking_average_precision,
    precision_at_k,
    rank_zero_shot,
    recall_at_k,
    top_k_jaccard,
)

ROOT = Path(__file__).parent
FOUNDATION_ROOT = ROOT.parent / "foundation"


def _resolve_path(path: str) -> str:
    if path.startswith("${"):
        end = path.find("}")
        if end != -1:
            value = os.environ.get(path[2:end], "")
            if value:
                return value + path[end + 1 :]
    return path


def _load_audio_segment(path: str, start: float, end: float) -> tuple[np.ndarray, int]:
    import soundfile as sf

    info = sf.info(path)
    start_sample = int(start * info.samplerate)
    end_sample = int(min(end, info.duration) * info.samplerate)
    data, sample_rate = sf.read(
        path,
        start=start_sample,
        stop=end_sample,
        dtype="float32",
    )
    if data.ndim > 1:
        data = data.mean(axis=1)
    return np.asarray(data, dtype=np.float32), int(sample_rate)


def summarize_prior_clap(result: dict[str, Any]) -> dict[str, Any]:
    """Summarize prompt-ranking diversity from the already-measured #332 result."""
    retrieval = result.get("text_retrieval") or {}
    per_query = retrieval.get("per_query_results") or []
    if not per_query:
        return {
            "available": False,
            "reason": "foundation result contains no text_retrieval queries",
        }

    top1_ids: list[str] = []
    top3_sets: list[set[str]] = []
    for query in per_query:
        ranked = query.get("ranked_results") or []
        if not ranked:
            continue
        top1_ids.append(str(ranked[0]["audio_id"]))
        top3_sets.append({str(row["audio_id"]) for row in ranked[:3]})

    pairwise_jaccard: list[float] = []
    for left_index in range(len(top3_sets)):
        for right_index in range(left_index + 1, len(top3_sets)):
            left = top3_sets[left_index]
            right = top3_sets[right_index]
            union = left | right
            pairwise_jaccard.append(len(left & right) / len(union) if union else 1.0)

    return {
        "available": bool(top1_ids),
        "num_queries": len(top1_ids),
        "unique_top1": len(set(top1_ids)),
        "unique_top1_fraction": round(len(set(top1_ids)) / len(top1_ids), 4) if top1_ids else None,
        "mean_pairwise_top3_jaccard": (
            round(float(np.mean(pairwise_jaccard)), 4) if pairwise_jaccard else None
        ),
        "interpretation": (
            "Prompt-ranking diversity diagnostic only. Low top-1 diversity or high "
            "top-3 overlap suggests collapsed prompt discrimination; it is not an "
            "accuracy score."
        ),
    }


def run_prior_evidence(
    foundation_result_path: Path | None = None,
    reference_metrics_path: Path | None = None,
) -> dict[str, Any]:
    if foundation_result_path is None:
        foundation_result_path = FOUNDATION_ROOT / "results" / "clap.json"
    if reference_metrics_path is None:
        reference_metrics_path = ROOT / "reference_metrics.json"

    with foundation_result_path.open() as handle:
        foundation_result = json.load(handle)
    with reference_metrics_path.open() as handle:
        reference_metrics = json.load(handle)

    operational = foundation_result.get("operational") or {}
    return {
        "evidence_class": "PRIOR_LOCAL_AND_REFERENCE_EVIDENCE",
        "clap": {
            "model_id": operational.get("model_id"),
            "weight_license": operational.get("weight_license"),
            "cpu_latency": operational.get("cpu_latency"),
            "prompt_ranking_diagnostic": summarize_prior_clap(foundation_result),
            "source": "backend/evaluation/analysis_v3/foundation/results/clap.json",
        },
        "essentia_reference": reference_metrics,
        "notes": (
            "No new model inference is performed by --task prior. CLAP operational and "
            "retrieval data were measured in #332; Essentia metrics are upstream reference "
            "benchmarks and are not hello-ai local measurements."
        ),
    }


def _text_embeddings(
    adapter: CLAPAdapter,
    taxonomy: dict[str, Any],
) -> tuple[list[str], np.ndarray]:
    labels = [str(label) for label in taxonomy["labels"]]
    template = str(taxonomy["prompt_template"])
    vectors: list[np.ndarray] = []
    for label in labels:
        result = adapter.embed_text(template.format(label=label))
        if result is None or not result.ok or result.vector is None:
            error = None if result is None else result.error
            raise RuntimeError(f"Failed to embed label {label!r}: {error}")
        vectors.append(np.asarray(result.vector, dtype=float))
    return labels, np.stack(vectors)


def _embed_audio(adapter: CLAPAdapter, audio: np.ndarray, sample_rate: int) -> np.ndarray:
    result = adapter.embed_audio(audio, sample_rate)
    if not result.ok or result.vector is None:
        raise RuntimeError(f"Failed to embed audio: {result.error}")
    return np.asarray(result.vector, dtype=float)


def _truth_row(labels: list[str], expected: list[str]) -> np.ndarray:
    expected_set = set(expected)
    return np.asarray([label in expected_set for label in labels], dtype=bool)


def run_zero_shot_probe(
    manifest_path: Path | None = None,
    device: str = "cpu",
) -> dict[str, Any]:
    """Run the opt-in CLAP context probe on rights-safe cached audio.

    This is a small product probe, not a substitute for MTG-Jamendo's standard
    test split. Raw cosine similarities are deliberately reported as `score`.
    """
    if manifest_path is None:
        manifest_path = ROOT / "manifests" / "context_probe.json"
    with manifest_path.open() as handle:
        manifest = json.load(handle)

    adapter = CLAPAdapter(device=device)
    adapter.load()
    taxonomy_embeddings = {
        name: _text_embeddings(adapter, taxonomy)
        for name, taxonomy in manifest["taxonomies"].items()
    }

    scored_truth: dict[str, list[np.ndarray]] = {name: [] for name in taxonomy_embeddings}
    scored_values: dict[str, list[np.ndarray]] = {name: [] for name in taxonomy_embeddings}
    clips: list[dict[str, Any]] = []

    for clip in manifest["clips"]:
        path = _resolve_path(str(clip["audio_path"]))
        if not os.path.exists(path):
            clips.append({"id": clip["id"], "status": "missing_audio", "path": path})
            continue

        start = float(clip["excerpt_start"])
        end = float(clip["excerpt_end"])
        audio, sample_rate = _load_audio_segment(path, start, end)
        audio_vector = _embed_audio(adapter, audio, sample_rate)
        clip_result: dict[str, Any] = {"id": clip["id"], "status": "ok", "taxonomies": {}}

        for taxonomy_name, (labels, text_vectors) in taxonomy_embeddings.items():
            ranking = rank_zero_shot(audio_vector, text_vectors, labels)
            score_by_label = {label: score for label, score in ranking}
            expected = [str(value) for value in clip.get("expected", {}).get(taxonomy_name, [])]
            clip_result["taxonomies"][taxonomy_name] = {
                "expected": expected,
                "ranked": [{"label": label, "score": round(score, 6)} for label, score in ranking],
                "scored": bool(expected),
            }
            if expected:
                scored_truth[taxonomy_name].append(_truth_row(labels, expected))
                scored_values[taxonomy_name].append(
                    np.asarray([score_by_label[label] for label in labels], dtype=float)
                )

        segment_seconds = float(manifest["segment_stability_seconds"])
        segment_stability: dict[str, Any] = {}
        segment_start = start
        segment_vectors: list[np.ndarray] = []
        while segment_start + segment_seconds <= end + 1e-9:
            segment_audio, segment_sr = _load_audio_segment(
                path,
                segment_start,
                min(segment_start + segment_seconds, end),
            )
            segment_vectors.append(_embed_audio(adapter, segment_audio, segment_sr))
            segment_start += segment_seconds

        for taxonomy_name, (labels, text_vectors) in taxonomy_embeddings.items():
            score_rows = []
            for vector in segment_vectors:
                ranking = rank_zero_shot(vector, text_vectors, labels)
                by_label = {label: score for label, score in ranking}
                score_rows.append([by_label[label] for label in labels])
            segment_stability[taxonomy_name] = {
                "num_segments": len(score_rows),
                "top3_adjacent_jaccard": (
                    round(top_k_jaccard(np.asarray(score_rows), min(3, len(labels))), 4)
                    if score_rows
                    else None
                ),
                "warning": "stability is not accuracy; constant predictions can look stable",
            }
        clip_result["segment_stability"] = segment_stability
        clips.append(clip_result)

    aggregate: dict[str, Any] = {}
    for taxonomy_name, (labels, _text_vectors) in taxonomy_embeddings.items():
        if not scored_truth[taxonomy_name]:
            aggregate[taxonomy_name] = {"num_scored_clips": 0}
            continue
        truth = np.stack(scored_truth[taxonomy_name])
        values = np.stack(scored_values[taxonomy_name])
        k = min(3, len(labels))
        aggregate[taxonomy_name] = {
            "num_scored_clips": int(len(truth)),
            "precision_at_1": round(precision_at_k(truth, values, 1), 4),
            f"precision_at_{k}": round(precision_at_k(truth, values, k), 4),
            f"recall_at_{k}": round(recall_at_k(truth, values, k), 4),
            "label_ranking_average_precision": round(
                label_ranking_average_precision(truth, values), 4
            ),
            "evidence_class": "QUALITATIVE_PRODUCT_PROBE",
        }

    return {
        "candidate": "clap",
        "model_id": adapter.model_id,
        "device": device,
        "manifest": manifest["name"],
        "raw_score_semantics": "cosine similarity; not calibrated confidence",
        "aggregate": aggregate,
        "clips": clips,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analysis V3 context evidence evaluation")
    parser.add_argument("--task", choices=["prior", "zero-shot"], default="prior")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.task == "prior":
        result = run_prior_evidence()
        default_name = "prior_evidence.json"
    else:
        result = run_zero_shot_probe(args.manifest, args.device)
        default_name = "clap_zero_shot.json"

    output = args.output or ROOT / "results" / default_name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print(f"Results saved to {output}")


if __name__ == "__main__":
    main()

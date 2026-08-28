"""Foundation model evaluation runner.

Usage:
  python -m backend.evaluation.analysis_v3.foundation.run --candidate mert
  python -m backend.evaluation.analysis_v3.foundation.run --candidate all
  python -m backend.evaluation.analysis_v3.foundation.run --candidate mert --task operational
  python -m backend.evaluation.analysis_v3.foundation.run --candidate mert --task retrieval
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from .adapters import ADAPTERS, FoundationModelAdapter
from .metrics import (
    OperationalResult,
    RuntimeMetrics,
    check_determinism,
    evaluate_cross_representation,
    evaluate_retrieval,
    generate_synthetic_audio,
    get_checkpoint_size,
    measure_embedding_latency,
)


def _load_adapter(candidate: str, device: str = "cpu") -> FoundationModelAdapter:
    if candidate not in ADAPTERS:
        raise ValueError(f"Unknown candidate: {candidate}. Available: {list(ADAPTERS.keys())}")
    adapter = ADAPTERS[candidate](device=device)
    return adapter


def _generate_probe_audio(probe: dict[str, Any], sample_rate: int = 24000) -> np.ndarray:
    duration = probe.get("duration_seconds", 10.0)
    freq = probe.get("frequency_hz", 440.0)
    harmonics = probe.get("harmonics", [1.0])
    amplitudes = probe.get("amplitudes", [1.0])
    seed = probe.get("seed", 42)

    rng = np.random.RandomState(seed)
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = np.zeros_like(t)

    for h, a in zip(harmonics, amplitudes):
        audio += a * np.sin(2 * np.pi * freq * h * t)

    onset = probe.get("onset_pattern", "sustained")
    if onset == "percussive":
        envelope = np.exp(-3.0 * t / duration)
        audio *= envelope
    elif onset == "legato":
        envelope = np.ones_like(t)
        fade_samples = int(0.05 * sample_rate)
        envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
        envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
        audio *= envelope
    elif onset == "syncopated":
        beat_freq = 2.0
        envelope = 0.5 + 0.5 * np.sin(2 * np.pi * beat_freq * t)
        audio *= envelope
    elif onset == "vibrato":
        vibrato = 1.0 + 0.02 * np.sin(2 * np.pi * 5.0 * t)
        audio *= vibrato
    elif onset == "crescendo":
        envelope = np.linspace(0.3, 1.0, len(t))
        audio *= envelope
    elif onset == "ornamented":
        ornament = 1.0 + 0.1 * np.sin(2 * np.pi * 8.0 * t)
        audio *= ornament

    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.8

    return audio.astype(np.float32)


def _generate_midi_bytes(pitches: list[int], duration: float, velocity: int = 80) -> bytes:
    import struct

    def _var_len(value: int) -> bytes:
        buf = bytearray()
        buf.append(value & 0x7F)
        value >>= 7
        while value:
            buf.append(0x80 | (value & 0x7F))
            value >>= 7
        buf.reverse()
        return bytes(buf)

    tempo_bpm = 120
    ppq = 480
    ticks_per_sec = ppq * tempo_bpm / 60.0

    events = []
    for i, pitch in enumerate(pitches):
        start_tick = int(i * duration * ticks_per_sec)
        end_tick = int((i + 1) * duration * ticks_per_sec)
        events.append((start_tick, pitch, velocity, True))
        events.append((end_tick, pitch, 0, False))
    events.sort(key=lambda e: e[0])

    track_data = bytearray()
    us_per_beat = int(60_000_000 / tempo_bpm)
    track_data.extend(_var_len(0))
    track_data.extend(bytes([0xFF, 0x51, 0x03]))
    track_data.extend(bytes([(us_per_beat >> 16) & 0xFF, (us_per_beat >> 8) & 0xFF, us_per_beat & 0xFF]))

    last_tick = 0
    for tick, pitch, vel, on in events:
        delta = tick - last_tick
        last_tick = tick
        track_data.extend(_var_len(delta))
        cmd = 0x90 if on else 0x80
        track_data.extend(bytes([cmd, pitch, vel]))

    track_data.extend(_var_len(0))
    track_data.extend(bytes([0xFF, 0x2F, 0x00]))

    header = struct.pack(">HHH", 0, 1, ppq)
    track_chunk = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)
    return b"MThd" + struct.pack(">I", 6) + header + track_chunk


def run_operational_evaluation(
    candidate: str,
    device: str = "cpu",
) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Operational evaluation: {candidate}")
    print(f"{'='*60}")

    result: dict[str, Any] = {
        "candidate": candidate,
        "device": device,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }

    try:
        adapter = _load_adapter(candidate, device)
        meta = adapter.metadata()
        result["model_id"] = meta.model_id
        result["code_license"] = meta.code_license
        result["weight_license"] = meta.weight_license
        result["training_data_notes"] = meta.training_data_notes
        result["embedding_dim"] = meta.embedding_dim
        result["temporal"] = meta.temporal
        result["supports_audio"] = meta.supports_audio
        result["supports_text"] = meta.supports_text
        result["supports_symbolic"] = meta.supports_symbolic
    except Exception as e:
        result["install_success"] = False
        result["install_error"] = str(e)
        return result

    result["install_success"] = True

    try:
        t0 = time.monotonic()
        adapter.load()
        result["load_success"] = True
        result["load_time_seconds"] = round(time.monotonic() - t0, 2)
    except Exception as e:
        result["load_success"] = False
        result["load_error"] = str(e)
        return result

    checkpoint_size = get_checkpoint_size(meta.model_id)
    if checkpoint_size:
        result["checkpoint_size_mb"] = round(checkpoint_size, 1)

    for duration_label, duration in [("10s", 10.0), ("30s", 30.0)]:
        audio = generate_synthetic_audio(duration_seconds=duration)
        metrics = measure_embedding_latency(adapter, audio, 24000, num_runs=2)
        result[f"cpu_latency_{duration_label}"] = {
            "latency_seconds": metrics.latency_seconds,
            "audio_duration_seconds": metrics.audio_duration_seconds,
            "error": metrics.error,
        }

    audio_10s = generate_synthetic_audio(duration_seconds=10.0)
    result["determinism_stable"] = check_determinism(adapter, audio_10s, 24000, num_runs=3)

    embed_result = adapter.embed_audio(audio_10s, 24000)
    if embed_result.ok:
        result["embedding_dim_measured"] = embed_result.dimensionality
        result["temporal_measured"] = embed_result.temporal_vectors is not None
        if embed_result.temporal_vectors is not None:
            result["temporal_vectors_shape"] = list(embed_result.temporal_vectors.shape)

    if adapter.supports_text():
        text_result = adapter.embed_text("solo piano")
        if text_result and text_result.ok:
            result["text_embedding_dim"] = text_result.dimensionality
        else:
            result["text_embedding_error"] = text_result.error if text_result else "no result"

    return result


def run_within_work_similarity(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Within-work similarity: {candidate}")
    print(f"{'='*60}")

    with open(manifest_path) as f:
        manifest = json.load(f)

    adapter = _load_adapter(candidate, device)
    adapter.load()

    embeddings: dict[str, np.ndarray] = {}
    for probe in manifest["probes"]:
        audio = _generate_probe_audio(probe)
        result = adapter.embed_audio(audio, 24000)
        if result.ok and result.vector is not None:
            embeddings[probe["id"]] = result.vector
            print(f"  Embedded {probe['id']}: dim={result.dimensionality}")
        else:
            print(f"  FAILED {probe['id']}: {result.error}")

    if len(embeddings) < 2:
        return {"error": "Insufficient embeddings for similarity evaluation"}

    from .metrics import compute_similarity_matrix

    ids = sorted(embeddings.keys())
    matrix = compute_similarity_matrix(embeddings)

    similarity_results: list[dict[str, Any]] = []
    for i, query_id in enumerate(ids):
        neighbors = []
        for j, neighbor_id in enumerate(ids):
            if i != j:
                neighbors.append({
                    "id": neighbor_id,
                    "similarity": round(float(matrix[i, j]), 4),
                })
        neighbors.sort(key=lambda x: x["similarity"], reverse=True)
        similarity_results.append({
            "query": query_id,
            "category": next(p["category"] for p in manifest["probes"] if p["id"] == query_id),
            "nearest_neighbors": neighbors[:3],
        })

    return {
        "candidate": candidate,
        "task": "within_work_similarity",
        "num_probes": len(embeddings),
        "similarity_matrix": {
            "ids": ids,
            "values": [[round(float(v), 4) for v in row] for row in matrix.tolist()],
        },
        "per_query_results": similarity_results,
        "notes": "Qualitative product probe. Similarity reflects embedding space structure, not musical accuracy.",
    }


def run_cross_work_similarity(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Cross-work similarity: {candidate}")
    print(f"{'='*60}")

    with open(manifest_path) as f:
        manifest = json.load(f)

    adapter = _load_adapter(candidate, device)
    adapter.load()

    embeddings: dict[str, np.ndarray] = {}
    for probe in manifest["probes"]:
        audio = _generate_probe_audio(probe)
        result = adapter.embed_audio(audio, 24000)
        if result.ok and result.vector is not None:
            embeddings[probe["id"]] = result.vector
            print(f"  Embedded {probe['id']}: dim={result.dimensionality}")
        else:
            print(f"  FAILED {probe['id']}: {result.error}")

    if len(embeddings) < 2:
        return {"error": "Insufficient embeddings for cross-work evaluation"}

    from .metrics import compute_similarity_matrix

    ids = sorted(embeddings.keys())
    matrix = compute_similarity_matrix(embeddings)

    cross_results: list[dict[str, Any]] = []
    for i, query_id in enumerate(ids):
        neighbors = []
        for j, neighbor_id in enumerate(ids):
            if i != j:
                neighbors.append({
                    "id": neighbor_id,
                    "category": next(p["category"] for p in manifest["probes"] if p["id"] == neighbor_id),
                    "similarity": round(float(matrix[i, j]), 4),
                })
        neighbors.sort(key=lambda x: x["similarity"], reverse=True)
        cross_results.append({
            "query": query_id,
            "query_category": next(p["category"] for p in manifest["probes"] if p["id"] == query_id),
            "nearest_neighbors": neighbors,
        })

    return {
        "candidate": candidate,
        "task": "cross_work_similarity",
        "num_probes": len(embeddings),
        "similarity_matrix": {
            "ids": ids,
            "values": [[round(float(v), 4) for v in row] for row in matrix.tolist()],
        },
        "per_query_results": cross_results,
        "notes": "Qualitative product probe. Different musical organizations should ideally show distinct clustering.",
    }


def run_text_retrieval(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Text retrieval: {candidate}")
    print(f"{'='*60}")

    with open(manifest_path) as f:
        manifest = json.load(f)

    adapter = _load_adapter(candidate, device)
    adapter.load()

    if not adapter.supports_text():
        return {
            "candidate": candidate,
            "task": "text_retrieval",
            "status": "unsupported",
            "notes": f"{candidate} does not support text embedding",
        }

    diversity_path = Path(manifest_path).parent / "diversity_probe.json"
    if not diversity_path.exists():
        return {"error": "Diversity probe manifest not found"}

    with open(diversity_path) as f:
        diversity_manifest = json.load(f)

    audio_embeddings: dict[str, np.ndarray] = {}
    for probe in diversity_manifest["probes"]:
        audio = _generate_probe_audio(probe)
        result = adapter.embed_audio(audio, 24000)
        if result.ok and result.vector is not None:
            audio_embeddings[probe["id"]] = result.vector

    text_embeddings: dict[str, np.ndarray] = {}
    for query in manifest["queries"]:
        result = adapter.embed_text(query["text"])
        if result and result.ok and result.vector is not None:
            text_embeddings[query["id"]] = result.vector
            print(f"  Embedded text '{query['text']}': dim={result.dimensionality}")

    if not audio_embeddings or not text_embeddings:
        return {"error": "Insufficient embeddings for text retrieval"}

    from .metrics import cosine_similarity

    retrieval_results: list[dict[str, Any]] = []
    for query_id, text_emb in text_embeddings.items():
        similarities: list[dict[str, Any]] = []
        for audio_id, audio_emb in audio_embeddings.items():
            sim = cosine_similarity(text_emb, audio_emb)
            similarities.append({
                "audio_id": audio_id,
                "category": next(p["category"] for p in diversity_manifest["probes"] if p["id"] == audio_id),
                "similarity": round(sim, 4),
            })
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        query_text = next(q["text"] for q in manifest["queries"] if q["id"] == query_id)
        retrieval_results.append({
            "query_id": query_id,
            "query_text": query_text,
            "ranked_results": similarities,
        })

    return {
        "candidate": candidate,
        "task": "text_retrieval",
        "num_queries": len(text_embeddings),
        "num_audio_candidates": len(audio_embeddings),
        "per_query_results": retrieval_results,
        "notes": "Qualitative probe. Text-to-audio retrieval reflects cross-modal alignment.",
    }


def run_cross_representation(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Cross-representation: {candidate}")
    print(f"{'='*60}")

    with open(manifest_path) as f:
        manifest = json.load(f)

    adapter = _load_adapter(candidate, device)
    adapter.load()

    if not adapter.supports_symbolic():
        return {
            "candidate": candidate,
            "task": "cross_representation",
            "status": "unsupported",
            "notes": f"{candidate} does not support symbolic (MIDI) embedding",
        }

    audio_embeddings: dict[str, np.ndarray] = {}
    midi_embeddings: dict[str, np.ndarray] = {}

    for pair in manifest["aligned_pairs"]:
        pair_id = pair["id"]

        audio_params = pair["audio_params"]
        if "frequencies" in audio_params:
            audio = _generate_probe_audio({
                "frequency_hz": audio_params["frequencies"][0],
                "harmonics": [1.0],
                "amplitudes": [1.0],
                "duration_seconds": audio_params.get("note_duration", 0.5) * len(audio_params["frequencies"]),
                "seed": hash(pair_id) % 10000,
            })
        else:
            audio = generate_synthetic_audio(duration_seconds=4.0)

        audio_result = adapter.embed_audio(audio, audio_params.get("sample_rate", 24000))
        if audio_result.ok and audio_result.vector is not None:
            audio_embeddings[pair_id] = audio_result.vector
            print(f"  Audio embedded: {pair_id}")

        midi_params = pair["midi_params"]
        if "pitches" in midi_params:
            midi_bytes = _generate_midi_bytes(
                midi_params["pitches"],
                midi_params.get("note_duration", 0.5),
                midi_params.get("velocity", 80),
            )
        else:
            midi_bytes = _generate_midi_bytes([60, 64, 67], 0.5)

        midi_result = adapter.embed_symbolic(midi_bytes)
        if midi_result and midi_result.ok and midi_result.vector is not None:
            midi_embeddings[pair_id] = midi_result.vector
            print(f"  MIDI embedded: {pair_id}")

    if not audio_embeddings or not midi_embeddings:
        return {"error": "Insufficient embeddings for cross-representation evaluation"}

    matched_pairs = [(pid, pid) for pid in audio_embeddings if pid in midi_embeddings]
    cross_result = evaluate_cross_representation(audio_embeddings, midi_embeddings, matched_pairs)

    return {
        "candidate": candidate,
        "task": "cross_representation",
        "num_pairs": len(matched_pairs),
        "results": cross_result,
        "notes": "Cross-modal alignment test. Matched audio/MIDI pairs should rank above mismatched pairs.",
    }


def run_candidate(
    candidate: str,
    task: str = "all",
    manifest_dir: str | None = None,
    device: str = "cpu",
    output_dir: str = "results",
) -> dict[str, Any]:
    if manifest_dir is None:
        manifest_dir = str(Path(__file__).parent / "manifests")

    results: dict[str, Any] = {
        "candidate": candidate,
        "task": task,
        "device": device,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if task in ("all", "operational"):
        results["operational"] = run_operational_evaluation(candidate, device)

    if task in ("all", "within_work"):
        manifest_path = os.path.join(manifest_dir, "diversity_probe.json")
        if os.path.exists(manifest_path):
            results["within_work"] = run_within_work_similarity(candidate, manifest_path, device)

    if task in ("all", "cross_work"):
        manifest_path = os.path.join(manifest_dir, "diversity_probe.json")
        if os.path.exists(manifest_path):
            results["cross_work"] = run_cross_work_similarity(candidate, manifest_path, device)

    if task in ("all", "text_retrieval"):
        manifest_path = os.path.join(manifest_dir, "product_queries.json")
        if os.path.exists(manifest_path):
            results["text_retrieval"] = run_text_retrieval(candidate, manifest_path, device)

    if task in ("all", "cross_representation"):
        manifest_path = os.path.join(manifest_dir, "aligned_representation_probe.json")
        if os.path.exists(manifest_path):
            results["cross_representation"] = run_cross_representation(candidate, manifest_path, device)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{candidate}.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Foundation model evaluation runner")
    parser.add_argument(
        "--candidate",
        required=True,
        choices=list(ADAPTERS.keys()) + ["all"],
        help="Candidate model to evaluate",
    )
    parser.add_argument(
        "--task",
        default="all",
        choices=["all", "operational", "within_work", "cross_work", "text_retrieval", "cross_representation"],
        help="Evaluation task to run",
    )
    parser.add_argument(
        "--manifest-dir",
        default=None,
        help="Directory containing manifest files",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "mps"],
        help="Device to run on",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for results",
    )
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = str(Path(__file__).parent / "results")

    if args.candidate == "all":
        for candidate in ADAPTERS:
            try:
                run_candidate(candidate, args.task, args.manifest_dir, args.device, args.output_dir)
            except Exception as e:
                print(f"\nFAILED {candidate}: {e}")
    else:
        run_candidate(args.candidate, args.task, args.manifest_dir, args.device, args.output_dir)


if __name__ == "__main__":
    main()

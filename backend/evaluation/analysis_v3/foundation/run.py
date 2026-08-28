"""Foundation model evaluation runner.

Usage:
  python -m backend.evaluation.analysis_v3.foundation.run --candidate mert
  python -m backend.evaluation.analysis_v3.foundation.run --candidate all
  python -m backend.evaluation.analysis_v3.foundation.run --candidate mert --task operational
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np

from .adapters import ADAPTERS, FoundationModelAdapter
from .metrics import (
    check_determinism,
    evaluate_cross_representation,
    generate_synthetic_audio,
    get_checkpoint_size,
    measure_embedding_latency,
)


def _load_adapter(candidate: str, device: str = "cpu") -> FoundationModelAdapter:
    if candidate not in ADAPTERS:
        raise ValueError(
            f"Unknown candidate: {candidate}. Available: {list(ADAPTERS.keys())}"
        )
    return ADAPTERS[candidate](device=device)


def _stable_seed(pair_id: str) -> int:
    """Deterministic seed from string using SHA-256 (not Python hash)."""
    digest = hashlib.sha256(pair_id.encode()).hexdigest()
    return int(digest[:8], 16)


def _resolve_path(path: str) -> str:
    """Resolve ${VAR}/rest style paths."""
    if path.startswith("${"):
        end = path.find("}")
        if end != -1:
            env_var = path[2:end]
            rest = path[end + 1:]
            expanded = os.environ.get(env_var, "")
            if expanded:
                return expanded + rest
    return path


def _load_audio_segment(
    audio_path: str,
    start: float,
    end: float,
    target_sr: int | None = None,
) -> tuple[np.ndarray, int]:
    """Load a segment of audio from a file."""
    import soundfile as sf

    info = sf.info(audio_path)
    sr = info.samplerate
    start_sample = int(start * sr)
    end_sample = int(min(end, info.duration) * sr)
    end_sample - start_sample

    data, sr = sf.read(
        audio_path,
        start=start_sample,
        stop=end_sample,
        dtype="float32",
    )
    if data.ndim > 1:
        data = data.mean(axis=1)

    if target_sr is not None and target_sr != sr:
        import torch
        import torchaudio

        waveform = torch.from_numpy(data).float().unsqueeze(0)
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=target_sr)
        data = resampler(waveform).squeeze(0).numpy()
        sr = target_sr

    return data, sr


def _extract_midi_segment(
    midi_path: str,
    start: float,
    end: float,
) -> bytes:
    """Extract MIDI events from [start, end) and serialize as valid MIDI.

    Uses pretty_midi (already in repo dependencies) to parse the MIDI file,
    extract notes whose time intersects [start, end), shift them to start at
    time 0, and serialize as a new MIDI file.
    """
    import io

    import pretty_midi

    pm = pretty_midi.PrettyMIDI(midi_path)

    new_pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    new_inst = pretty_midi.Instrument(program=0, is_drum=False)

    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            if note.end <= start or note.start >= end:
                continue
            clipped_start = max(note.start, start) - start
            clipped_end = min(note.end, end) - start
            if clipped_end - clipped_start <= 0:
                continue
            new_inst.notes.append(
                pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=clipped_start,
                    end=clipped_end,
                )
            )

    new_pm.instruments.append(new_inst)
    buf = io.BytesIO()
    new_pm.write(buf)
    return buf.getvalue()


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
        "arch": platform.machine(),
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

    latency_results: dict[str, Any] = {}
    for duration_label, duration in [("10s", 10.0), ("30s", 30.0)]:
        audio = generate_synthetic_audio(duration_seconds=duration)
        metrics = measure_embedding_latency(adapter, audio, 24000, num_runs=5)
        latency_results[duration_label] = {
            "latency_seconds": metrics.latency_seconds,
            "audio_duration_seconds": metrics.audio_duration_seconds,
            "error": metrics.error,
        }
    result["cpu_latency"] = latency_results

    audio_10s = generate_synthetic_audio(duration_seconds=10.0)
    result["determinism_stable"] = check_determinism(
        adapter, audio_10s, 24000, num_runs=3
    )

    embed_result = adapter.embed_audio(audio_10s, 24000)
    if embed_result.ok:
        result["embedding_dim_measured"] = embed_result.dimensionality
        result["temporal_measured"] = embed_result.temporal_vectors is not None
        if embed_result.temporal_vectors is not None:
            result["temporal_vectors_shape"] = list(
                embed_result.temporal_vectors.shape
            )

    if adapter.supports_text():
        text_result = adapter.embed_text("solo piano")
        if text_result and text_result.ok:
            result["text_embedding_dim"] = text_result.dimensionality
        else:
            result["text_embedding_error"] = (
                text_result.error if text_result else "no result"
            )

    return result


def run_within_work_similarity(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
) -> dict[str, Any]:
    """Within-work retrieval: embed windows from one real work, retrieve others."""
    print(f"\n{'='*60}")
    print(f"Within-work similarity: {candidate}")
    print(f"{'='*60}")

    with open(manifest_path) as f:
        manifest = json.load(f)

    ww = manifest.get("within_work")
    if not ww:
        return {"error": "No within_work section in manifest"}

    adapter = _load_adapter(candidate, device)
    adapter.load()

    audio_path = _resolve_path(ww["audio_path"])
    if not os.path.exists(audio_path):
        return {"error": f"Audio file not found: {audio_path}"}

    import soundfile as sf

    info = sf.info(audio_path)
    work_duration = info.duration
    sr = info.samplerate

    window_sec = ww.get("window_seconds", 10.0)
    hop_sec = ww.get("hop_seconds", 5.0)
    query_starts = ww.get("query_windows", [0, 60, 120])
    query_labels = ww.get("description_windows", [])

    all_windows: list[dict[str, Any]] = []
    t = 0.0
    idx = 0
    while t + window_sec <= work_duration:
        all_windows.append({
            "idx": idx,
            "start": t,
            "end": t + window_sec,
            "label": f"window_{idx:03d}_{t:.0f}s",
        })
        t += hop_sec
        idx += 1

    print(f"  Total windows: {len(all_windows)}")

    embeddings: dict[str, np.ndarray] = {}
    for w in all_windows:
        audio, _ = _load_audio_segment(audio_path, w["start"], w["end"])
        result = adapter.embed_audio(audio, sr)
        if result.ok and result.vector is not None:
            embeddings[w["label"]] = result.vector
        else:
            print(f"  FAILED {w['label']}: {result.error}")

    if len(embeddings) < 2:
        return {"error": "Insufficient embeddings"}

    from .metrics import retrieve_nearest_neighbors

    query_results: list[dict[str, Any]] = []
    for qi, qstart in enumerate(query_starts):
        qwin = None
        for w in all_windows:
            if abs(w["start"] - qstart) < 1.0:
                qwin = w
                break
        if qwin is None:
            continue

        qlabel = qwin["label"]
        if qlabel not in embeddings:
            continue

        neighbors = retrieve_nearest_neighbors(
            qlabel, embeddings, top_k=10
        )

        nn_table: list[dict[str, Any]] = []
        for nid, sim in neighbors:
            nw = next((w for w in all_windows if w["label"] == nid), None)
            nn_table.append({
                "window": nid,
                "start": nw["start"] if nw else None,
                "end": nw["end"] if nw else None,
                "similarity": round(sim, 4),
            })

        qdesc = query_labels[qi] if qi < len(query_labels) else f"query at {qstart}s"
        query_results.append({
            "query_window": qlabel,
            "query_start": qstart,
            "query_description": qdesc,
            "nearest_neighbors": nn_table,
        })

    return {
        "candidate": candidate,
        "task": "within_work_similarity",
        "work_id": ww.get("work_id", "unknown"),
        "work_duration_seconds": round(work_duration, 1),
        "num_windows": len(all_windows),
        "num_embeddings": len(embeddings),
        "window_seconds": window_sec,
        "hop_seconds": hop_sec,
        "per_query_results": query_results,
        "notes": (
            "QUALITATIVE PRODUCT PROBE. "
            "Within-work segment retrieval from one real musical work. "
            "No objective ground truth; inspect nearest-neighbor tables for musical plausibility."
        ),
    }


def run_cross_work_similarity(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
) -> dict[str, Any]:
    """Cross-work similarity using real music from diversity probe."""
    print(f"\n{'='*60}")
    print(f"Cross-work similarity: {candidate}")
    print(f"{'='*60}")

    with open(manifest_path) as f:
        manifest = json.load(f)

    adapter = _load_adapter(candidate, device)
    adapter.load()

    embeddings: dict[str, np.ndarray] = {}
    probe_meta: dict[str, dict[str, Any]] = {}

    for probe in manifest["probes"]:
        audio_path = _resolve_path(probe["audio_path"])
        if not os.path.exists(audio_path):
            print(f"  SKIP {probe['id']}: file not found")
            continue

        start = probe.get("excerpt_start", 0.0)
        end = probe.get("excerpt_end", 20.0)
        target_sr = probe.get("sample_rate", 24000)

        try:
            audio, sr = _load_audio_segment(audio_path, start, end, target_sr=target_sr)
            result = adapter.embed_audio(audio, sr)
            if result.ok and result.vector is not None:
                embeddings[probe["id"]] = result.vector
                probe_meta[probe["id"]] = {
                    "category": probe["category"],
                    "dataset": probe["dataset"],
                    "description": probe.get("description", ""),
                }
                print(f"  Embedded {probe['id']}: dim={result.dimensionality}")
            else:
                print(f"  FAILED {probe['id']}: {result.error}")
        except Exception as e:
            print(f"  FAILED {probe['id']}: {e}")

    if len(embeddings) < 2:
        return {"error": "Insufficient embeddings for cross-work evaluation"}

    from .metrics import compute_similarity_matrix, retrieve_nearest_neighbors

    ids = sorted(embeddings.keys())
    matrix = compute_similarity_matrix(embeddings)

    cross_results: list[dict[str, Any]] = []
    for _i, query_id in enumerate(ids):
        neighbors = retrieve_nearest_neighbors(query_id, embeddings, top_k=len(ids) - 1)
        nn_table = []
        for nid, sim in neighbors:
            nn_table.append({
                "id": nid,
                "category": probe_meta.get(nid, {}).get("category", ""),
                "dataset": probe_meta.get(nid, {}).get("dataset", ""),
                "similarity": round(sim, 4),
            })
        cross_results.append({
            "query": query_id,
            "query_category": probe_meta.get(query_id, {}).get("category", ""),
            "nearest_neighbors": nn_table,
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
        "notes": (
            "QUALITATIVE PRODUCT PROBE. "
            "Cross-work similarity using real music from established corpora. "
            "Inspect ranking behavior; do not interpret absolute cosine ranges as quality."
        ),
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
        audio_path = _resolve_path(probe["audio_path"])
        if not os.path.exists(audio_path):
            continue
        start = probe.get("excerpt_start", 0.0)
        end = probe.get("excerpt_end", 20.0)
        target_sr = probe.get("sample_rate", 24000)
        try:
            audio, sr = _load_audio_segment(audio_path, start, end, target_sr=target_sr)
            result = adapter.embed_audio(audio, sr)
            if result.ok and result.vector is not None:
                audio_embeddings[probe["id"]] = result.vector
        except Exception:
            continue

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
            probe = next(
                p for p in diversity_manifest["probes"] if p["id"] == audio_id
            )
            similarities.append({
                "audio_id": audio_id,
                "category": probe["category"],
                "similarity": round(sim, 4),
            })
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        query_text = next(
            q["text"] for q in manifest["queries"] if q["id"] == query_id
        )
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
        "notes": (
            "QUALITATIVE PRODUCT PROBE. "
            "Text-to-audio retrieval using real music. "
            "Inspect ranking plausibility."
        ),
    }


def run_cross_representation(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
) -> dict[str, Any]:
    """Cross-representation: audio <-> MIDI alignment using real aligned pairs."""
    print(f"\n{'='*60}")
    print(f"Cross-representation: {candidate}")
    print(f"{'='*60}")

    adapter = _load_adapter(candidate, device)
    adapter.load()

    if not adapter.supports_symbolic():
        return {
            "candidate": candidate,
            "task": "cross_representation",
            "status": "unsupported",
            "notes": f"{candidate} does not support symbolic (MIDI) embedding",
        }

    diversity_path = Path(manifest_path).parent / "diversity_probe.json"
    with open(diversity_path) as f:
        diversity_manifest = json.load(f)

    ww = diversity_manifest.get("within_work", {})
    maestro_audio = _resolve_path(ww.get("audio_path", ""))
    maestro_midi = _resolve_path(ww.get("midi_path", ""))

    audio_embeddings: dict[str, np.ndarray] = {}
    midi_embeddings: dict[str, np.ndarray] = {}

    if os.path.exists(maestro_audio) and os.path.exists(maestro_midi):
        print("  Using real MAESTRO aligned audio/MIDI pairs")
        window_sec = 10.0
        hop_sec = 30.0
        import soundfile as sf

        info = sf.info(maestro_audio)
        duration = info.duration
        sr = info.samplerate

        t = 30.0
        pair_idx = 0
        while t + window_sec <= min(duration, 180.0):
            pair_id = f"maestro_pair_{pair_idx}"
            try:
                audio, _ = _load_audio_segment(maestro_audio, t, t + window_sec)
                audio_result = adapter.embed_audio(audio, sr)
                if audio_result.ok and audio_result.vector is not None:
                    audio_embeddings[pair_id] = audio_result.vector
                    print(f"    Audio embedded: {pair_id}")

                midi_bytes = _extract_midi_segment(maestro_midi, t, t + window_sec)
                midi_result = adapter.embed_symbolic(midi_bytes)
                if midi_result and midi_result.ok and midi_result.vector is not None:
                    midi_embeddings[pair_id] = midi_result.vector
                    print(f"    MIDI embedded: {pair_id}")
            except Exception as e:
                print(f"    FAILED {pair_id}: {e}")
                raise

            t += hop_sec
            pair_idx += 1

    if not audio_embeddings or not midi_embeddings:
        return {"error": "Insufficient embeddings for cross-representation evaluation"}

    matched_pairs = [(pid, pid) for pid in audio_embeddings if pid in midi_embeddings]
    cross_result = evaluate_cross_representation(
        audio_embeddings, midi_embeddings, matched_pairs
    )

    return {
        "candidate": candidate,
        "task": "cross_representation",
        "num_pairs": len(matched_pairs),
        "method": "real_aligned_maestro_audio_midi",
        "results": cross_result,
        "notes": (
            "QUALITATIVE PRODUCT PROBE. "
            "Cross-modal alignment using real MAESTRO aligned audio/MIDI. "
            "Audio segments from real recording; MIDI from aligned MAESTRO MIDI."
        ),
    }


def _generate_midi_bytes(
    pitches: list[int], duration: float, velocity: int = 80
) -> bytes:
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
    track_data.extend(
        bytes([
            (us_per_beat >> 16) & 0xFF,
            (us_per_beat >> 8) & 0xFF,
            us_per_beat & 0xFF,
        ])
    )

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
            results["within_work"] = run_within_work_similarity(
                candidate, manifest_path, device
            )

    if task in ("all", "cross_work"):
        manifest_path = os.path.join(manifest_dir, "diversity_probe.json")
        if os.path.exists(manifest_path):
            results["cross_work"] = run_cross_work_similarity(
                candidate, manifest_path, device
            )

    if task in ("all", "text_retrieval"):
        manifest_path = os.path.join(manifest_dir, "product_queries.json")
        if os.path.exists(manifest_path):
            results["text_retrieval"] = run_text_retrieval(
                candidate, manifest_path, device
            )

    if task in ("all", "cross_representation"):
        manifest_path = os.path.join(
            manifest_dir, "aligned_representation_probe.json"
        )
        if os.path.exists(manifest_path):
            results["cross_representation"] = run_cross_representation(
                candidate, manifest_path, device
            )

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
        choices=[
            "all",
            "operational",
            "within_work",
            "cross_work",
            "text_retrieval",
            "cross_representation",
        ],
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
                run_candidate(
                    candidate,
                    args.task,
                    args.manifest_dir,
                    args.device,
                    args.output_dir,
                )
            except Exception as e:
                print(f"\nFAILED {candidate}: {e}")
    else:
        run_candidate(
            args.candidate,
            args.task,
            args.manifest_dir,
            args.device,
            args.output_dir,
        )


if __name__ == "__main__":
    main()

"""Basic Pitch parameter benchmark and cleanup ablation runner.

Usage:
  python -m evaluation.benchmark --manifest path/to/manifest.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

from evaluation.corpus import load_manifest
from evaluation.models import CorpusManifest
from evaluation.transcription_metrics import Note, compute_note_metrics


def _midi_to_notes(midi_bytes: bytes) -> list[Note]:
    import io

    import pretty_midi

    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    return [
        Note(pitch=n.pitch, start=n.start, end=n.end, velocity=n.velocity)
        for inst in pm.instruments
        for n in inst.notes
        if not inst.is_drum
    ]


def benchmark_thresholds(
    manifest_path: str,
    output_path: str,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    onset_values = [0.3, 0.4, 0.5, 0.6, 0.7]
    frame_values = [0.1, 0.2, 0.3, 0.4, 0.5]

    results: dict[str, dict[str, Any]] = {}
    for onset in onset_values:
        for frame in frame_values:
            key = f"onset={onset}_frame={frame}"
            results[key] = _run_config(manifest, onset, frame)

    summary = {
        "corpus": manifest.name,
        "clips": len(manifest.clips),
        "configs": results,
        "by_category": _group_by_category(manifest, results),
    }
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary


def _run_config(
    manifest: CorpusManifest,
    onset: float,
    frame: float,
) -> dict[str, Any]:
    import sys
    from pathlib import Path

    backend_dir = str(Path(__file__).resolve().parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from music_features import transcribe_audio

    results: dict[str, dict[str, Any]] = {}
    for clip in manifest.clips:
        audio_bytes = Path(clip.audio).read_bytes()
        t0 = time.monotonic()
        tr = transcribe_audio(audio_bytes, fmt="wav", onset_threshold=onset, frame_threshold=frame)
        elapsed = time.monotonic() - t0
        if clip.reference_midi:
            ref_bytes = Path(clip.reference_midi).read_bytes()
            ref_notes = _midi_to_notes(ref_bytes)
            pred_notes = [Note.from_dict(n) for n in tr.get("notes", [])]
            metrics = compute_note_metrics(pred_notes, ref_notes).to_dict()
        else:
            metrics = None
        results[clip.id] = {
            "num_notes": tr["num_notes"],
            "cleanup": tr.get("cleanup_report", {}),
            "time_s": round(elapsed, 2),
            "metrics": metrics,
        }
    return results


def benchmark_cleanup_ablation(
    manifest_path: str,
    output_path: str,
) -> dict[str, Any]:
    import sys
    from pathlib import Path

    backend_dir = str(Path(__file__).resolve().parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from music_features import _clean_midi

    manifest = load_manifest(manifest_path)
    results: dict[str, Any] = {}
    for clip in manifest.clips:
        audio_bytes = Path(clip.audio).read_bytes()
        tr = _raw_basic_pitch(audio_bytes)
        raw_notes = _midi_to_notes(tr["raw_midi"])
        cleaned_midi, report = _clean_midi(tr["raw_midi"])
        cleaned_notes = _midi_to_notes(cleaned_midi)
        ref_notes = None
        raw_m = cleaned_m = None
        if clip.reference_midi:
            ref_bytes = Path(clip.reference_midi).read_bytes()
            ref_notes = _midi_to_notes(ref_bytes)
            raw_m = compute_note_metrics(raw_notes, ref_notes).to_dict()
            cleaned_m = compute_note_metrics(cleaned_notes, ref_notes).to_dict()
        results[clip.id] = {
            "raw_note_count": len(raw_notes),
            "cleaned_note_count": len(cleaned_notes),
            "cleanup_report": report,
            "raw_metrics": raw_m,
            "cleaned_metrics": cleaned_m,
        }
    summary = {"corpus": manifest.name, "clips": len(manifest.clips), "results": results}
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary


def _raw_basic_pitch(audio_bytes: bytes) -> dict[str, Any]:
    import os
    import tempfile

    from basic_pitch.inference import predict

    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "input.wav")
        with open(in_path, "wb") as f:
            f.write(audio_bytes)
        out_dir = os.path.join(td, "out")
        os.makedirs(out_dir, exist_ok=True)
        _, midi_data, _ = predict(in_path)
        midi_path = os.path.join(out_dir, "input.mid")
        midi_data.write(midi_path)
        with open(midi_path, "rb") as f:
            raw_midi = f.read()
    notes_count = len(midi_data.instruments[0].notes) if midi_data.instruments else 0
    return {"raw_midi": raw_midi, "num_notes_raw": notes_count}


def _group_by_category(
    manifest: CorpusManifest,
    results: dict[str, Any],
) -> dict[str, Any]:
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for clip in manifest.clips:
        cat = clip.category
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append({"id": clip.id})
    for cat, _items in by_cat.items():
        best_f1 = 0.0
        best_config = ""
        current_f1 = 0.0
        for config_key, config_results in results.items():
            if clip.id not in config_results:
                continue
            m = config_results[clip.id].get("metrics")
            if m:
                f1 = m.get("onset_note_f1", 0)
                if f1 > best_f1:
                    best_f1 = f1
                    best_config = config_key
                if config_key == "onset=0.5_frame=0.3":
                    current_f1 = f1
        by_cat[cat] = {
            "current_f1": round(current_f1, 4),
            "best_f1": round(best_f1, 4),
            "best_config": best_config,
        }
    return by_cat


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="evaluation/results/benchmark.json")
    parser.add_argument("--ablation", default="evaluation/results/cleanup_ablation.json")
    parser.add_argument("--mode", choices=["thresholds", "ablation", "all"], default="all")
    args = parser.parse_args()

    if args.mode in ("thresholds", "all"):
        print("Benchmarking Basic Pitch thresholds...")
        summary = benchmark_thresholds(args.manifest, args.output)
        print(json.dumps(summary.get("by_category", {}), indent=2))

    if args.mode in ("ablation", "all"):
        print("\nCleanup ablation...")
        summary = benchmark_cleanup_ablation(args.manifest, args.ablation)
        for clip_id, r in summary["results"].items():
            raw_f1 = r["raw_metrics"]["onset_note_f1"] if r["raw_metrics"] else "N/A"
            clean_f1 = r["cleaned_metrics"]["onset_note_f1"] if r["cleaned_metrics"] else "N/A"
            print(
                f"  {clip_id}: raw={raw_f1} → clean={clean_f1}"
                f" ({r['raw_note_count']}→{r['cleaned_note_count']} notes)"
            )


if __name__ == "__main__":
    main()

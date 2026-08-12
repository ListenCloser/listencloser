"""Basic Pitch parameter benchmark and cleanup ablation runner.

Usage:
  python -m evaluation.benchmark --manifest path/to/manifest.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from evaluation.corpus import load_manifest
from evaluation.models import CorpusManifest, EvalClip
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


def _transcribe_raw(manifest: CorpusManifest, onset: float, frame: float) -> dict[str, Any]:
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
            m = compute_note_metrics(pred_notes, ref_notes).to_dict()
        else:
            m = None
        results[clip.id] = {
            "num_notes": tr["num_notes"],
            "time_s": round(elapsed, 2),
            "metrics": m,
        }
    return results


def benchmark_thresholds(manifest_path: str, output_path: str) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    onset_values = [0.3, 0.4, 0.5, 0.6, 0.7]
    frame_values = [0.1, 0.2, 0.3, 0.4, 0.5]
    configs: dict[str, dict[str, Any]] = {}
    for onset in onset_values:
        for frame in frame_values:
            key = f"onset={onset}_frame={frame}"
            configs[key] = _transcribe_raw(manifest, onset, frame)
    by_cat = _group_by_category(manifest, configs)
    summary = {"corpus": manifest.name, "clips": len(manifest.clips), "by_category": by_cat}
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary


def benchmark_cleanup_ablation(manifest_path: str, output_path: str) -> dict[str, Any]:
    import io

    import pretty_midi

    manifest = load_manifest(manifest_path)
    onset, frame = 0.5, 0.3

    def raw_transcribe(clip: EvalClip) -> tuple[bytes, int]:
        audio_bytes = Path(clip.audio).read_bytes()
        with tempfile.TemporaryDirectory() as td:
            in_path = os.path.join(td, "input.wav")
            with open(in_path, "wb") as f:
                f.write(audio_bytes)
            out_dir = os.path.join(td, "out")
            os.makedirs(out_dir, exist_ok=True)
            from basic_pitch.inference import predict
            _, midi_data, _ = predict(in_path, onset_threshold=onset, frame_threshold=frame)
            midi_path = os.path.join(out_dir, "input.mid")
            midi_data.write(midi_path)
            with open(midi_path, "rb") as f:
                raw = f.read()
            return raw, len(midi_data.instruments[0].notes) if midi_data.instruments else 0

    def clean_config(midi_bytes: bytes, remove_short=True, remove_low_vel=True,
                     remove_range=True, merge=True) -> tuple[bytes, dict]:
        m = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
        report: dict[str, int | str] = {
            "profile": (
                f"abl_s{int(remove_short)}_v{int(remove_low_vel)}"
                f"_r{int(remove_range)}_m{int(merge)}"
            ),
            "input_notes": 0, "kept_notes": 0,
            "removed_short": 0, "removed_low_velocity": 0,
            "removed_out_of_range": 0, "merged_overlaps": 0,
        }
        for inst in m.instruments:
            if inst.is_drum:
                continue
            report["input_notes"] = int(report["input_notes"]) + len(inst.notes)
            filtered = list(inst.notes)
            if remove_range:
                filtered = [n for n in filtered if _MIN_PITCH <= n.pitch <= _MAX_PITCH]
                report["removed_out_of_range"] = int(report["removed_out_of_range"]) + (
                    int(report["input_notes"]) - len(filtered)
                )
            if remove_short:
                filtered = [n for n in filtered if (n.end - n.start) >= _MIN_DUR]
                report["removed_short"] = int(report["removed_short"]) + (
                    int(report["input_notes"]) - len(filtered)
                    - int(report["removed_out_of_range"])
                )
            if remove_low_vel:
                filtered = [n for n in filtered if not (
                    n.velocity < _LOW_VEL and (n.end - n.start) < _LOW_VEL_SHORT
                )]
                report["removed_low_velocity"] = int(report["removed_low_velocity"]) + (
                    int(report["input_notes"]) - len(filtered)
                    - int(report["removed_out_of_range"]) - int(report["removed_short"])
                )
            if merge:
                filtered.sort(key=lambda n: (n.pitch, n.start))
                cleaned = []
                for note in filtered:
                    if (
                        not cleaned
                        or note.pitch != cleaned[-1].pitch
                        or note.start >= cleaned[-1].end
                    ):
                        cleaned.append(note)
                    else:
                        cleaned[-1].end = max(cleaned[-1].end, note.end)
                        cleaned[-1].velocity = max(cleaned[-1].velocity, note.velocity)
                        report["merged_overlaps"] = int(report["merged_overlaps"]) + 1
                filtered = cleaned
            inst.notes = filtered
            report["kept_notes"] = int(report["kept_notes"]) + len(inst.notes)
        buf = io.BytesIO()
        m.write(buf)
        return buf.getvalue(), report

    results: dict[str, dict[str, Any]] = {}
    for clip in manifest.clips:
        raw_midi, raw_count = raw_transcribe(clip)
        ref_notes = None
        if clip.reference_midi:
            ref_bytes = Path(clip.reference_midi).read_bytes()
            ref_notes = _midi_to_notes(ref_bytes)
        clip_r: dict[str, Any] = {"raw_count": raw_count}
        configs = [
            ("none", (False, False, False, False)),
            ("all", (True, True, True, True)),
            ("no_short", (False, True, True, True)),
            ("no_lowvel", (True, False, True, True)),
            ("no_range", (True, True, False, True)),
            ("no_merge", (True, True, True, False)),
        ]
        for name, (rs, rv, rr, rm) in configs:
            cl, rep = clean_config(
                raw_midi, remove_short=rs, remove_low_vel=rv, remove_range=rr, merge=rm
            )
            cl_notes = _midi_to_notes(cl)
            m = compute_note_metrics(cl_notes, ref_notes).to_dict() if ref_notes else None
            f1_val = m["note_f1"] if m else None
            clip_r[name] = {"count": len(cl_notes), "report": rep, "f1": f1_val}
        results[clip.id] = clip_r

    summary = {"corpus": manifest.name, "clips": len(manifest.clips), "results": results}
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary



_MIN_DUR = 0.075
_MIN_PITCH = 21
_MAX_PITCH = 108
_LOW_VEL = 18
_LOW_VEL_SHORT = 0.16


def _group_by_category(
    manifest: CorpusManifest, configs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cats: dict[str, list[str]] = {}
    for clip in manifest.clips:
        cats.setdefault(clip.category, []).append(clip.id)
    by_cat: dict[str, Any] = {}
    for cat, clip_ids in cats.items():
        results: dict[str, Any] = {}
        for key in configs:
            f1s = []
            runtimes = []
            for cid in clip_ids:
                m = configs[key].get(cid, {}).get("metrics")
                t = configs[key].get(cid, {}).get("time_s", 0)
                if m:
                    f1s.append(m["note_f1"])
                runtimes.append(t)
            results[key] = {
                "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else None,
                "avg_time_s": round(sum(runtimes) / len(runtimes), 2) if runtimes else 0,
            }
        current_f1 = results.get("onset=0.5_frame=0.3", {}).get("macro_f1")
        best = max(results.items(), key=lambda kv: kv[1].get("macro_f1") or 0)
        by_cat[cat] = {
            "clip_count": len(clip_ids),
            "current_f1": current_f1,
            "best_f1": best[1]["macro_f1"],
            "best_config": best[0],
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
        s = benchmark_thresholds(args.manifest, args.output)
        print(json.dumps(s.get("by_category", {}), indent=2))
    if args.mode in ("ablation", "all"):
        print("\nCleanup ablation...")
        s = benchmark_cleanup_ablation(args.manifest, args.ablation)
        for cid, r in s["results"].items():
            none_f1 = r["none"].get("f1")
            all_f1 = r["all"].get("f1")
            print(f"  {cid}: none={none_f1} → all={all_f1}")


if __name__ == "__main__":
    main()

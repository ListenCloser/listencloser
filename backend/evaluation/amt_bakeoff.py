"""AMT engine bakeoff: Basic Pitch vs alternative OSS engines.

Run:
  MUSIC_EVAL_CACHE_DIR=... python -m evaluation.amt_bakeoff

Compares engines on BabySlakh isolated piano stems (where a piano-specialist is
applicable) and recomputes the Basic Pitch baseline on guitar + full-mix.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from evaluation.amt_engines import ENGINES
from evaluation.datasets import cache
from evaluation.datasets.parsers import parse_babyslakh_midi
from evaluation.slicing import slice_samples
from evaluation.transcription_metrics import Note, compute_note_metrics


def _yaml_stems(path: Path) -> dict[str, dict[str, Any]]:
    import yaml

    with open(path) as fh:
        return yaml.safe_load(fh).get("stems", {})


def _piano_stems(track_dir: Path) -> list[str]:
    meta = _yaml_stems(track_dir / "metadata.yaml")
    return [sid for sid, info in meta.items() if info.get("inst_class") == "Piano"]


def _stem_audio(track_dir: Path, stem_id: str, start: float, end: float) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(track_dir / "stems" / f"{stem_id}.wav"))
    if data.ndim > 1:
        data = data.mean(axis=1)
    return slice_samples(data, sr, start, end).astype(np.float32), sr


def _stem_reference(track_dir: Path, stem_id: str, start: float, end: float) -> list[Note]:
    midi = track_dir / "MIDI" / f"{stem_id}.mid"
    notes = parse_babyslakh_midi(midi.read_bytes(), exclude_drums=True)
    clipped: list[Note] = []
    for n in notes:
        if n["start"] >= end or n["end"] <= start:
            continue
        cs = max(n["start"], start) - start
        ce = min(n["end"], end) - start
        if ce - cs <= 1e-6:
            continue
        clipped.append(Note(n["pitch"], cs, ce, n.get("velocity", 80)))
    return clipped


def _metrics(pred: list[Note], ref: list[Note]) -> dict[str, Any]:
    if not ref:
        return None
    m = compute_note_metrics(pred, ref)
    return {
        "onset_f1": round(m.onset_f1, 4),
        "note_f1": round(m.note_f1, 4),
        "onset_precision": round(m.onset_precision, 4),
        "onset_recall": round(m.onset_recall, 4),
        "note_precision": round(m.note_precision, 4),
        "note_recall": round(m.note_recall, 4),
        "excessive_rate": round(m.excessive_count / max(m.predicted_count, 1), 4),
        "missed_rate": round(m.missed_count / max(m.reference_count, 1), 4),
        "predicted": m.predicted_count,
        "reference": m.reference_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AMT engine bakeoff")
    parser.add_argument(
        "--tracks", default="Track00001,Track00002,Track00003,Track00004,Track00005"
    )
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=20.0)
    args = parser.parse_args()

    prepared = cache.cache_dir() / "babyslakh" / "babyslakh_16k"
    tracks = args.tracks.split(",")

    # Collect piano-stem clip instances across tracks.
    instances: list[tuple[str, str]] = []
    for track in tracks:
        for sid in _piano_stems(prepared / track):
            instances.append((track, sid))

    results: list[dict[str, Any]] = []
    for track, sid in instances:
        track_dir = prepared / track
        audio, sr = _stem_audio(track_dir, sid, args.start, args.end)
        ref = _stem_reference(track_dir, sid, args.start, args.end)
        entry: dict[str, Any] = {
            "track": track,
            "stem": sid,
            "category": "piano_stem",
            "reference_notes": len(ref),
        }

        for engine_name in ("basic_pitch", "byte_piano"):
            fn = ENGINES[engine_name]["fn"]
            t0 = time.monotonic()
            try:
                pred = fn(audio, sr)
                entry[engine_name] = _metrics(pred, ref)
                entry[f"{engine_name}_time_s"] = round(time.monotonic() - t0, 2)
            except Exception as exc:
                entry[engine_name] = {"error": str(exc)}
                entry[f"{engine_name}_time_s"] = None
        results.append(entry)
        print(json.dumps(entry))

    # Aggregate by engine over piano stems.
    agg: dict[str, Any] = {}
    for engine_name in ("basic_pitch", "byte_piano"):
        vals = [
            r[engine_name]
            for r in results
            if isinstance(r.get(engine_name), dict) and "error" not in r[engine_name]
        ]
        if vals:
            n = len(vals)
            agg[engine_name] = {
                "clips": n,
                "onset_f1": round(sum(v["onset_f1"] for v in vals) / n, 4),
                "note_f1": round(sum(v["note_f1"] for v in vals) / n, 4),
                "excessive_rate": round(sum(v["excessive_rate"] for v in vals) / n, 4),
                "missed_rate": round(sum(v["missed_rate"] for v in vals) / n, 4),
            }
    print("\n=== Piano-stem aggregate ===")
    print(json.dumps(agg, indent=2))

    out = cache.cache_dir() / "amt-bakeoff.json"
    out.write_text(json.dumps({"results": results, "aggregate": agg}, indent=2))


if __name__ == "__main__":
    main()

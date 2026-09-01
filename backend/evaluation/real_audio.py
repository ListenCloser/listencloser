"""Production-Auto transcription evaluation: GuitarSet + BabySlakh.

Run with data already in MUSIC_EVAL_CACHE_DIR:

  MUSIC_EVAL_CACHE_DIR=... python -m evaluation.real_audio --corpus real_audio_v1

Runs the exact production ``auto`` profile through the engine registry and
reports note/onset F1 by category (guitar vs full_mix). This is deliberately
not an engine-adapter bakeoff: a result is evidence about the product default.
"""

from __future__ import annotations

import argparse
import io
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from engines.base import TranscriptionEngine
from engines.registry import get_transcription_engine
from evaluation.datasets import cache
from evaluation.datasets.babyslakh import load_babyslakh_notes
from evaluation.datasets.guitarset import load_guitarset_notes
from evaluation.datasets.registry import resolve_clip
from evaluation.slicing import slice_samples
from evaluation.transcription_metrics import Note, compute_note_metrics


def _load_clips(corpus: str) -> list[dict[str, Any]]:
    corpora_dir = Path(__file__).resolve().parent / "corpora"
    with open(corpora_dir / f"{corpus}.json") as fh:
        return json.load(fh)["clips"]


def _reference_notes(clip: dict[str, Any], prepared: Path) -> list[Note]:
    start = float(clip.get("excerpt_start", 0.0))
    end = float(clip.get("excerpt_end", 30.0))
    if clip["dataset"] == "guitarset":
        jams_path = prepared / "guitarset" / "annotation" / f"{clip['source_id']}.jams"
        notes = load_guitarset_notes(str(jams_path))
    else:
        midi_path = prepared / "babyslakh" / "extracted" / clip["source_id"] / "all_src.mid"
        notes = load_babyslakh_notes(str(midi_path))
    clipped: list[Note] = []
    for n in notes:
        if n["start"] >= end or n["end"] <= start:
            continue
        clipped_start = max(n["start"], start) - start
        clipped_end = min(n["end"], end) - start
        if clipped_end - clipped_start <= 1e-6:
            continue
        clipped.append(
            Note(
                pitch=n["pitch"],
                start=clipped_start,
                end=clipped_end,
                velocity=n.get("velocity", 80),
            )
        )
    return clipped


def _transcribe_auto(
    wav_bytes: bytes,
    *,
    engine_factory: Callable[..., TranscriptionEngine] = get_transcription_engine,
) -> tuple[list[Note], dict[str, Any]]:
    """Run the exact product-default transcription route for one excerpt."""
    result = engine_factory(profile="auto").transcribe(wav_bytes, fmt="wav")
    return [Note.from_dict(note) for note in result.notes], result.provenance.to_dict()


def _slice_audio(audio_path: Path, start: float, end: float) -> bytes:
    data, sr = sf.read(str(audio_path))
    if data.ndim > 1:
        data = data.mean(axis=1)
    sliced = slice_samples(data, sr, start, end).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, sliced, sr, format="WAV")
    return buf.getvalue()


def run_production_auto(
    corpus: str,
    *,
    engine_factory: Callable[..., TranscriptionEngine] = get_transcription_engine,
) -> list[dict[str, Any]]:
    prepared = cache.cache_dir()
    clips = _load_clips(corpus)
    results: list[dict[str, Any]] = []
    for clip in clips:
        clip_id = clip["id"]
        try:
            resolved = resolve_clip(clip)
            audio_path = Path(resolved.audio_path)
            start = float(clip.get("excerpt_start", 0.0))
            end = float(clip.get("excerpt_end", 30.0))
            wav_bytes = _slice_audio(audio_path, start, end)
            ref = _reference_notes(clip, prepared)

            t0 = time.monotonic()
            pred, provenance = _transcribe_auto(wav_bytes, engine_factory=engine_factory)
            elapsed = time.monotonic() - t0

            m = compute_note_metrics(pred, ref) if ref else None
            results.append(
                {
                    "id": clip_id,
                    "status": "ok",
                    "category": clip["category"],
                    "requested_profile": "auto",
                    "effective_engine": provenance["engine"],
                    "provenance": provenance,
                    "predicted_notes": len(pred),
                    "reference_notes": len(ref),
                    "time_s": round(elapsed, 2),
                    "metrics": m.to_dict() if m else None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": clip_id,
                    "status": "error",
                    "category": clip["category"],
                    "message": str(exc),
                }
            )
    return results


def _category_summary(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        if r.get("status") != "ok" or not r.get("metrics"):
            continue
        by_cat.setdefault(r["category"], []).append(r)
    summary: dict[str, dict[str, Any]] = {}
    for cat, items in by_cat.items():
        n = len(items)
        summary[cat] = {
            "clip_count": n,
            "note_f1": round(sum(i["metrics"]["note_f1"] for i in items) / n, 4),
            "onset_f1": round(sum(i["metrics"]["onset_f1"] for i in items) / n, 4),
            "excessive_rate": round(
                sum(
                    i["metrics"]["excessive_count"] / max(i["metrics"]["predicted_count"], 1)
                    for i in items
                )
                / n,
                4,
            ),
            "missed_rate": round(
                sum(
                    i["metrics"]["missed_count"] / max(i["metrics"]["reference_count"], 1)
                    for i in items
                )
                / n,
                4,
            ),
            "avg_runtime_s": round(sum(i["time_s"] for i in items) / n, 2),
        }
    return summary


def _result_payload(corpus: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "evaluation_id": "production_auto_real_audio_v1",
        "requested_profile": "auto",
        "corpus": corpus,
        "summary": _category_summary(results),
        "rows": results,
        "notes": [
            "Rows run the production transcription engine registry with profile=auto.",
            "Per-clip metrics require aligned reference notes; errors remain explicit.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the production Auto transcription path")
    parser.add_argument("--corpus", default="real_audio_v1")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the complete per-clip evidence payload as JSON.",
    )
    args = parser.parse_args()

    results = run_production_auto(args.corpus)
    payload = _result_payload(args.corpus, results)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n")
        print(args.output)

    print(json.dumps(payload["summary"], indent=2))
    for r in results:
        m = r.get("metrics")
        if m:
            print(
                f"{r['id']} [{r['category']}, {r['effective_engine']}]: noteF1={m['note_f1']} "
                f"pred={m['predicted_count']} ref={m['reference_count']} "
                f"t={r['time_s']}s"
            )
        else:
            print(f"{r['id']} [{r['category']}]: {r['status']} ({r.get('message', '')})")


if __name__ == "__main__":
    main()

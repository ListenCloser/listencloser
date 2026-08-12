"""Real-world corpus benchmark: run the production baseline and report by category.

This is a MANUAL quality benchmark, not a CI step. Run on a machine with the
production music dependencies (Basic Pitch, pretty_midi, soundfile) and the
prepared corpus:

  python -m evaluation.datasets.prepare --corpus real_world_v1
  python -m evaluation.real_world --corpus real_world_v1

Writes machine-readable JSON + Markdown to evaluation/reports/.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from evaluation.datasets import cache
from evaluation.transcription_metrics import Note, compute_note_metrics

_ONSET = 0.5
_FRAME = 0.3


def _load_clips(corpus: str) -> list[dict[str, Any]]:
    corpora_dir = Path(__file__).resolve().parent / "corpora"
    with open(corpora_dir / f"{corpus}.json") as fh:
        data = json.load(fh)
    return data["clips"]


def _prepared_dir(corpus: str) -> Path:
    return cache.cache_dir() / "prepared" / corpus


def _reference_notes(prepared_dir: Path, clip_id: str) -> list[Note]:
    midi_path = prepared_dir / f"{clip_id}.mid"
    if not midi_path.exists():
        return []

    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    return [
        Note(pitch=n.pitch, start=n.start, end=n.end, velocity=n.velocity)
        for inst in pm.instruments
        for n in inst.notes
        if not inst.is_drum
    ]


def _transcribe(audio_bytes: bytes, onset: float, frame: float) -> dict[str, Any]:
    import sys

    backend_dir = str(Path(__file__).resolve().parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from music_features import transcribe_audio

    return transcribe_audio(audio_bytes, fmt="wav", onset_threshold=onset, frame_threshold=frame)


def _metric_block(pred: list[Note], ref: list[Note]) -> dict[str, Any] | None:
    if not ref:
        return None
    m = compute_note_metrics(pred, ref)
    d = m.to_dict()
    d["excessive_rate"] = round(m.excessive_count / max(m.predicted_count, 1), 4)
    d["missed_rate"] = round(m.missed_count / max(m.reference_count, 1), 4)
    return d


def run_baseline(corpus: str) -> dict[str, Any]:
    prepared_dir = _prepared_dir(corpus)
    clips = _load_clips(corpus)
    results: list[dict[str, Any]] = []
    for clip in clips:
        clip_id = clip["id"]
        audio_path = prepared_dir / f"{clip_id}.wav"
        if not audio_path.exists():
            results.append({"id": clip_id, "status": "missing", "category": clip["category"]})
            continue
        ref = _reference_notes(prepared_dir, clip_id)
        try:
            t0 = time.monotonic()
            tr = _transcribe(audio_path.read_bytes(), _ONSET, _FRAME)
            elapsed = time.monotonic() - t0
            pred = [Note.from_dict(n) for n in tr.get("notes", [])]
            results.append(
                {
                    "id": clip_id,
                    "status": "ok",
                    "category": clip["category"],
                    "predicted_notes": len(pred),
                    "reference_notes": len(ref),
                    "time_s": round(elapsed, 2),
                    "metrics": _metric_block(pred, ref),
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
    return {"corpus": corpus, "config": {"onset": _ONSET, "frame": _FRAME}, "results": results}


def _category_summary(results: list[dict[str, Any]], metric: str) -> dict[str, dict[str, Any]]:
    by_cat: dict[str, list[float]] = {}
    for r in results:
        if r.get("status") != "ok" or not r.get("metrics"):
            continue
        v = r["metrics"].get(metric)
        if isinstance(v, (int, float)):
            by_cat.setdefault(r["category"], []).append(float(v))
    return {
        cat: {
            "clip_count": len(vals),
            "macro": round(sum(vals) / len(vals), 4) if vals else None,
        }
        for cat, vals in by_cat.items()
    }


def run_threshold_sweep(corpus: str) -> dict[str, Any]:
    """Sweep onset/frame thresholds on the prepared corpus (by category)."""
    prepared_dir = _prepared_dir(corpus)
    clips = _load_clips(corpus)
    onset_values = [0.3, 0.4, 0.5, 0.6, 0.7]
    frame_values = [0.1, 0.2, 0.3, 0.4, 0.5]

    per_config: dict[str, dict[str, Any]] = {}
    for onset in onset_values:
        for frame in frame_values:
            key = f"onset={onset}_frame={frame}"
            cat_f1s: dict[str, list[float]] = {}
            for clip in clips:
                audio_path = prepared_dir / f"{clip['id']}.wav"
                if not audio_path.exists():
                    continue
                ref = _reference_notes(prepared_dir, clip["id"])
                if not ref:
                    continue
                tr = _transcribe(audio_path.read_bytes(), onset, frame)
                pred = [Note.from_dict(n) for n in tr.get("notes", [])]
                m = compute_note_metrics(pred, ref)
                cat_f1s.setdefault(clip["category"], []).append(m.note_f1)
            per_config[key] = {cat: round(sum(v) / len(v), 4) for cat, v in cat_f1s.items() if v}

    # Best config per category (by note F1).
    best_by_cat: dict[str, dict[str, Any]] = {}
    for key, cats in per_config.items():
        for cat, f1 in cats.items():
            if cat not in best_by_cat or f1 > best_by_cat[cat]["f1"]:
                best_by_cat[cat] = {"config": key, "f1": f1}
    current = per_config.get(f"onset={_ONSET}_frame={_FRAME}", {})
    return {"current": current, "best_by_category": best_by_cat, "grid": per_config}


def run_cleanup_ablation(corpus: str) -> dict[str, Any]:
    """Reuse the PR #198 cleanup ablation on the prepared corpus."""
    import sys

    backend_dir = str(Path(__file__).resolve().parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from evaluation.benchmark import benchmark_cleanup_ablation

    # benchmark_cleanup_ablation expects a manifest path; write a temp manifest
    # pointing at the prepared slices.
    clips = _load_clips(corpus)
    tmp_manifest = cache.cache_dir() / f"prepared-manifest-{corpus}.json"
    manifest_clips = [
        {
            "id": c["id"],
            "audio": f"prepared/{corpus}/{c['id']}.wav",
            "category": c["category"],
            "reference_midi": f"prepared/{corpus}/{c['id']}.mid",
        }
        for c in clips
    ]
    tmp_manifest.write_text(json.dumps({"name": corpus, "clips": manifest_clips}, indent=2))
    try:
        return benchmark_cleanup_ablation(
            str(tmp_manifest), str(cache.cache_dir() / f"ablation-{corpus}.json")
        )
    finally:
        tmp_manifest.unlink(missing_ok=True)


def _write_report(payload: dict[str, Any], corpus: str) -> tuple[str, str]:
    reports_dir = Path(__file__).resolve().parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"{corpus}.json"
    md_path = reports_dir / f"{corpus}.md"
    json_path.write_text(json.dumps(payload, indent=2))

    baseline = payload["baseline"]
    lines = [f"# Real-world evaluation: {corpus}", ""]
    lines.append("## Transcription baseline (note/onset F1)")
    lines.append("| Category | Clips | Note F1 | Onset F1 | Excessive rate | Missed rate |")
    lines.append("|----------|-------|---------|----------|----------------|-------------|")
    for cat, info in _category_summary(baseline["results"], "note_f1").items():
        onset = _category_summary(baseline["results"], "onset_f1").get(cat, {}).get("macro")
        exc = _category_summary(baseline["results"], "excessive_rate").get(cat, {}).get("macro")
        miss = _category_summary(baseline["results"], "missed_rate").get(cat, {}).get("macro")
        lines.append(
            f"| {cat} | {info['clip_count']} | {info['macro']} | {onset} | {exc} | {miss} |"
        )
    lines.append("")
    lines.append("## Threshold sweep (best config per category)")
    lines.append(json.dumps(payload["threshold_sweep"]["best_by_category"], indent=2))
    lines.append("")
    lines.append("## Cleanup ablation")
    lines.append("```json")
    lines.append(json.dumps(payload["cleanup_ablation"], indent=2)[:4000])
    lines.append("```")
    lines.append("")
    lines.append(
        "> See the JSON report for per-clip detail. Run via `python -m evaluation.real_world`."
    )
    md_path.write_text("\n".join(lines))
    return str(json_path), str(md_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real-world quality benchmark")
    parser.add_argument("--corpus", default="real_world_v1")
    parser.add_argument(
        "--mode",
        choices=["baseline", "sweep", "ablation", "all"],
        default="baseline",
    )
    args = parser.parse_args()

    baseline = run_baseline(args.corpus)
    payload: dict[str, Any] = {"baseline": baseline}

    if args.mode in ("sweep", "all"):
        payload["threshold_sweep"] = run_threshold_sweep(args.corpus)
    if args.mode in ("ablation", "all"):
        payload["cleanup_ablation"] = run_cleanup_ablation(args.corpus)

    j, m = _write_report(payload, args.corpus)
    print(json.dumps(_category_summary(baseline["results"], "note_f1"), indent=2))
    print(f"JSON: {j}")
    print(f"Markdown: {m}")


if __name__ == "__main__":
    main()

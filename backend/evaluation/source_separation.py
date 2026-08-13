"""Source-separation vs direct transcription benchmark (BabySlakh full mixes).

Run:
  MUSIC_EVAL_CACHE_DIR=... python -m evaluation.source_separation

Compares:
  A  baseline        mixture -> Basic Pitch
  B  other-only      Demucs "other" stem -> Basic Pitch
  C  vocals+other    Demucs vocals+other -> Basic Pitch (merged)
  D  all-pitched     Demucs bass+other+vocals -> Basic Pitch (merged)
  O  oracle          ground-truth pitched stems -> Basic Pitch (merged)

Separated stems are cached under the cache dir so re-runs skip Demucs.
"""

from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from evaluation.datasets import cache
from evaluation.datasets.babyslakh import load_babyslakh_notes
from evaluation.merge import merge_notes, raw_concat
from evaluation.separation import PITCHED_SOURCES, separate
from evaluation.slicing import slice_note_dicts, slice_samples
from evaluation.transcription_metrics import Note, compute_note_metrics

_MODEL = "htdemucs"


def _baby_tracks(prepared: Path) -> list[str]:
    extracted = prepared / "babyslakh" / "extracted"
    return sorted(p.name for p in extracted.iterdir() if p.is_dir())


def _load_mix(prepared: Path, track: str, start: float, end: float) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(prepared / "babyslakh" / "extracted" / track / "mix.wav"))
    if data.ndim > 1:
        data = data.mean(axis=1)
    sliced = slice_samples(data, sr, start, end).astype(np.float32)
    return sliced, sr


def _reference(prepared: Path, track: str, start: float, end: float) -> list[Note]:
    midi = prepared / "babyslakh" / "extracted" / track / "all_src.mid"
    notes = load_babyslakh_notes(str(midi))  # excludes drums; list of dicts
    clipped = slice_note_dicts(notes, start, end)
    return [Note(n["pitch"], n["start"], n["end"], n.get("velocity", 80)) for n in clipped]


def _oracle_pitched_stems(prepared: Path, track: str) -> list[Path]:
    """Ground-truth BabySlakh stems, excluding drums (via metadata.yaml)."""
    # Full extraction lives under babyslakh_16k/<track>/; the adapter's
    # extracted/ dir only carries mix.wav + all_src.mid.
    track_dir = prepared / "babyslakh" / "babyslakh_16k" / track
    if not track_dir.exists():
        track_dir = prepared / "babyslakh" / "extracted" / track
    meta = _yaml_stem_flags(track_dir / "metadata.yaml")
    stems_dir = track_dir / "stems"
    pitched: list[Path] = []
    for s in sorted(stems_dir.glob("*.wav")):
        stem_id = s.stem  # e.g. "S00"
        if meta.get(stem_id, {}).get("is_drum", False):
            continue
        pitched.append(s)
    return pitched


def _yaml_stem_flags(path: Path) -> dict[str, dict[str, Any]]:
    import yaml

    with open(path) as fh:
        doc = yaml.safe_load(fh)
    return doc.get("stems", {})


def _transcribe(wav: np.ndarray, sr: int, onset: float, frame: float) -> list[Note]:
    import sys

    backend_dir = str(Path(__file__).resolve().parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from music_features import transcribe_with_engine

    buf = io.BytesIO()
    sf.write(buf, wav, sr, format="WAV")
    tr = transcribe_with_engine(
        buf.getvalue(), fmt="wav", onset_threshold=onset, frame_threshold=frame
    )
    return [Note.from_dict(n) for n in tr.get("notes", [])]


def _cached_stems(prepared: Path, track: str, start: float, end: float) -> dict[str, np.ndarray]:
    """Separate a clip, caching stems to the cache dir."""
    cache_dir = cache.cache_dir() / "separation" / _MODEL / track
    cache_dir.mkdir(parents=True, exist_ok=True)
    marker = cache_dir / "meta.json"
    stems: dict[str, np.ndarray] = {}
    if marker.exists():
        with open(marker) as fh:
            cached = json.load(fh)
        if cached.get("start") == start and cached.get("end") == end:
            for name in PITCHED_SOURCES + ("drums",):
                stem_file = cache_dir / f"{name}.npy"
                if stem_file.exists():
                    stems[name] = np.load(stem_file)
            if len(stems) == 4:
                return stems

    wav, sr = _load_mix(prepared, track, start, end)
    stems = separate(wav, sr, model_name=_MODEL)
    for name, stem in stems.items():
        np.save(cache_dir / f"{name}.npy", stem)
    with open(marker, "w") as fh:
        json.dump({"start": start, "end": end, "model": _MODEL}, fh)
    return stems


def _run_clip(
    prepared: Path,
    track: str,
    start: float,
    end: float,
    onset: float,
    frame: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {"track": track}
    ref = _reference(prepared, track, start, end)

    mix, sr = _load_mix(prepared, track, start, end)

    # A — baseline
    t0 = time.monotonic()
    pred = _transcribe(mix, sr, onset, frame)
    result["baseline_time_s"] = round(time.monotonic() - t0, 2)
    result["baseline"] = _metrics(pred, ref)

    # Separation (cached)
    t0 = time.monotonic()
    stems = _cached_stems(prepared, track, start, end)
    result["separation_time_s"] = round(time.monotonic() - t0, 2)

    model_sr = 44100

    # B — other only
    t0 = time.monotonic()
    other_pred = _transcribe(stems["other"], model_sr, onset, frame)
    result["other_time_s"] = round(time.monotonic() - t0, 2)
    result["other"] = _metrics(other_pred, ref)

    # C — vocals + other (raw + dedup)
    t0 = time.monotonic()
    c_preds = [_transcribe(stems[k], model_sr, onset, frame) for k in ("vocals", "other")]
    result["vocals_other_time_s"] = round(time.monotonic() - t0, 2)
    result["vocals_other_raw"] = _metrics(raw_concat(c_preds), ref)
    result["vocals_other_dedup"] = _metrics(merge_notes(c_preds), ref)

    # D — all pitched (raw + dedup)
    t0 = time.monotonic()
    d_preds = [_transcribe(stems[k], model_sr, onset, frame) for k in PITCHED_SOURCES]
    result["all_pitched_time_s"] = round(time.monotonic() - t0, 2)
    result["all_pitched_raw"] = _metrics(raw_concat(d_preds), ref)
    result["all_pitched_dedup"] = _metrics(merge_notes(d_preds), ref)

    # O — oracle (ground-truth pitched stems)
    oracle_paths = _oracle_pitched_stems(prepared, track)
    t0 = time.monotonic()
    o_preds = []
    for p in oracle_paths:
        d, sr2 = sf.read(str(p))
        if d.ndim > 1:
            d = d.mean(axis=1)
        sl = slice_samples(d, sr2, start, end).astype(np.float32)
        o_preds.append(_transcribe(sl, sr2, onset, frame))
    result["oracle_time_s"] = round(time.monotonic() - t0, 2)
    result["oracle_raw"] = _metrics(raw_concat(o_preds), ref) if o_preds else None
    result["oracle_dedup"] = _metrics(merge_notes(o_preds), ref) if o_preds else None

    result["reference_notes"] = len(ref)
    return result


def _metrics(pred: list[Note], ref: list[Note]) -> dict[str, Any]:
    if not ref:
        return None
    m = compute_note_metrics(pred, ref)
    return {
        "onset_f1": m.onset_f1,
        "note_f1": m.note_f1,
        "onset_precision": m.onset_precision,
        "onset_recall": m.onset_recall,
        "note_precision": m.note_precision,
        "note_recall": m.note_recall,
        "excessive_rate": m.excessive_count / max(m.predicted_count, 1),
        "missed_rate": m.missed_count / max(m.reference_count, 1),
        "predicted": m.predicted_count,
        "reference": m.reference_count,
    }


def _aggregate(results: list[dict[str, Any]], key: str) -> dict[str, Any]:
    vals = [r[key] for r in results if r.get(key)]
    if not vals:
        return {}
    n = len(vals)
    return {
        "onset_f1": round(sum(v["onset_f1"] for v in vals) / n, 4),
        "note_f1": round(sum(v["note_f1"] for v in vals) / n, 4),
        "excessive_rate": round(sum(v["excessive_rate"] for v in vals) / n, 4),
        "missed_rate": round(sum(v["missed_rate"] for v in vals) / n, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run source-separation benchmark")
    parser.add_argument(
        "--tracks",
        default="Track00001,Track00002,Track00003,Track00004,Track00005",
    )
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=20.0)
    parser.add_argument("--onset", type=float, default=0.5)
    parser.add_argument("--frame", type=float, default=0.3)
    args = parser.parse_args()

    prepared = cache.cache_dir()
    tracks = args.tracks.split(",")
    _metric_keys = {
        "baseline",
        "other",
        "vocals_other_raw",
        "vocals_other_dedup",
        "all_pitched_raw",
        "all_pitched_dedup",
        "oracle_raw",
        "oracle_dedup",
    }
    results = []
    for track in tracks:
        r = _run_clip(prepared, track, args.start, args.end, args.onset, args.frame)
        results.append(r)
        print(json.dumps({k: v for k, v in r.items() if k not in _metric_keys}))

    report = {
        "model": _MODEL,
        "configs": {
            "baseline": _aggregate(results, "baseline"),
            "other": _aggregate(results, "other"),
            "vocals_other_raw": _aggregate(results, "vocals_other_raw"),
            "vocals_other_dedup": _aggregate(results, "vocals_other_dedup"),
            "all_pitched_raw": _aggregate(results, "all_pitched_raw"),
            "all_pitched_dedup": _aggregate(results, "all_pitched_dedup"),
            "oracle_raw": _aggregate(results, "oracle_raw"),
            "oracle_dedup": _aggregate(results, "oracle_dedup"),
        },
        "results": results,
    }
    out = cache.cache_dir() / "separation-report.json"
    out.write_text(json.dumps(report, indent=2))
    print("\n=== Aggregate ===")
    print(json.dumps(report["configs"], indent=2))


if __name__ == "__main__":
    main()

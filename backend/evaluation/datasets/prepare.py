"""CLI to prepare (download/slice/cache) the real-world evaluation corpus.

Usage:
  python -m evaluation.datasets.prepare --corpus real_world_v1

Resolves each pinned clip via its dataset adapter, slices it to its excerpt
window, and writes rebased audio/MIDI/annotations into the cache. Skips clips
that are already prepared. Fails with a clear message when a dataset requires
manual acquisition.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.datasets import cache
from evaluation.datasets.registry import (
    ManualAcquisitionError,
    UnsupportedDatasetError,
    resolve_clip,
)
from evaluation.slicing import slice_audio, slice_beat_annotations, slice_midi


def _manifest_path(name: str) -> Path:
    corpora_dir = Path(__file__).resolve().parent.parent / "corpora"
    return corpora_dir / f"{name}.json"


def prepare_corpus(corpus: str, dataset: str | None = None) -> dict:
    manifest_file = _manifest_path(corpus)
    with open(manifest_file) as fh:
        data = json.load(fh)

    prepared_dir = cache.cache_dir() / "prepared" / corpus
    prepared_dir.mkdir(parents=True, exist_ok=True)

    clips = data["clips"]
    if dataset:
        clips = [c for c in clips if c["dataset"] == dataset]
        if not clips:
            raise SystemExit(f"no clips for dataset '{dataset}' in corpus '{corpus}'")

    results: list[dict] = []
    for clip in clips:
        entry = {"id": clip["id"], "dataset": clip["dataset"], "status": "ok"}
        try:
            resolved = resolve_clip(clip)
            start = float(clip.get("excerpt_start", 0.0))
            end = float(clip.get("excerpt_end", 30.0))

            audio_bytes = Path(resolved.audio_path).read_bytes()
            should_slice = start > 0 or end < float("inf")
            audio_sliced = slice_audio(audio_bytes, start, end) if should_slice else audio_bytes
            audio_out = prepared_dir / f"{clip['id']}.wav"
            audio_out.write_bytes(audio_sliced)
            entry["audio"] = str(audio_out)

            if resolved.reference_midi_path:
                midi_bytes = Path(resolved.reference_midi_path).read_bytes()
                midi_sliced, notes = slice_midi(midi_bytes, start, end)
                midi_out = prepared_dir / f"{clip['id']}.mid"
                midi_out.write_bytes(midi_sliced)
                entry["reference_midi"] = str(midi_out)
                entry["note_count"] = len(notes)

            if resolved.beats_path:
                beats, downbeats = _read_beat_annotations(resolved.beats_path)
                s_beats, s_dbs = slice_beat_annotations(beats, downbeats, start, end)
                ann_out = prepared_dir / f"{clip['id']}.beats.json"
                ann_out.write_text(json.dumps({"beats": s_beats, "downbeats": s_dbs}))
                entry["beats"] = str(ann_out)
        except ManualAcquisitionError as exc:
            entry["status"] = "manual"
            entry["message"] = str(exc)
        except UnsupportedDatasetError as exc:
            entry["status"] = "unsupported"
            entry["message"] = str(exc)
        except Exception as exc:
            entry["status"] = "error"
            entry["message"] = str(exc)
        results.append(entry)

    summary = {
        "corpus": corpus,
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "manual": sum(1 for r in results if r["status"] == "manual"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "clips": results,
    }
    out = cache.cache_dir() / f"prepared-{corpus}.json"
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def _read_beat_annotations(path: str) -> tuple[list[float], list[float]]:
    """Read ASAP TSV annotations into all beat times and downbeat times.

    ASAP stores the timestamp in columns 1 and 2 and the annotation label in
    column 3. ``db`` is both a beat and a downbeat; ``bR`` remains a beat even
    when the score does not admit a standard beat position.
    """
    beats: list[float] = []
    downbeats: list[float] = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                parts = line.split(maxsplit=2)
            if len(parts) < 3:
                continue
            try:
                timestamp = float(parts[0])
            except ValueError:
                continue
            label = parts[2].split(",", 1)[0].strip()
            if label in {"b", "db", "bR"}:
                beats.append(timestamp)
            if label == "db":
                downbeats.append(timestamp)
    return beats, downbeats


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the evaluation corpus")
    parser.add_argument("--corpus", default="real_world_v1")
    parser.add_argument("--dataset", help="restrict preparation to one dataset")
    args = parser.parse_args()
    prepare_corpus(args.corpus, args.dataset)


if __name__ == "__main__":
    main()

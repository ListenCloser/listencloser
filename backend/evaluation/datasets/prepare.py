"""CLI to prepare (download/slice/cache) the real-world evaluation corpus.

Usage:
  python -m evaluation.datasets.prepare --corpus real_world_v1

Resolves each pinned clip via its dataset adapter, slices it to its excerpt
window, and writes rebased audio/MIDI/annotations into the cache. Acquisition
status and evaluator-ready materialized clips are emitted as separate files so
manual/error rows can remain explicit without becoming invalid ``EvalClip``s.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.datasets import cache
from evaluation.datasets.registry import (
    ManualAcquisitionError,
    UnsupportedDatasetError,
    resolve_clip,
)
from evaluation.slicing import slice_audio, slice_beat_annotations, slice_midi

_MATERIALIZED_PROVENANCE_FIELDS = (
    "id",
    "category",
    "dataset",
    "split",
    "source_id",
    "license",
    "audio_provenance",
    "metrics",
    "excerpt_start",
    "excerpt_end",
)
_TEMPORAL_REFERENCE_FIELDS = ("beats", "downbeats", "chords", "sections")


def _manifest_path(name: str) -> Path:
    corpora_dir = Path(__file__).resolve().parent.parent / "corpora"
    return corpora_dir / f"{name}.json"


def _materialized_clip(
    clip: dict[str, Any],
    entry: dict[str, Any],
    *,
    beats: list[float] | None = None,
    downbeats: list[float] | None = None,
) -> dict[str, Any] | None:
    """Build one evaluator-ready clip from a successful preparation row.

    Prepared audio, MIDI, and beat evidence are rebased to excerpt time zero.
    ``excerpt_start``/``excerpt_end`` are retained only as source provenance.
    Full-piece MusicXML is intentionally not copied: it is not an excerpt-
    aligned reference for a rebased 20–25 second clip. Other source-timeline
    reference arrays are omitted unless preparation explicitly rebases them.
    """
    if entry.get("status") != "ok" or not entry.get("audio"):
        return None

    materialized = {
        field: clip[field]
        for field in _MATERIALIZED_PROVENANCE_FIELDS
        if field in clip and clip[field] is not None
    }
    materialized["audio"] = str(Path(entry["audio"]).resolve())
    if entry.get("reference_midi"):
        materialized["reference_midi"] = str(Path(entry["reference_midi"]).resolve())

    reference = dict(clip.get("reference") or {})
    for field in _TEMPORAL_REFERENCE_FIELDS:
        reference.pop(field, None)
    if beats is not None:
        reference["beats"] = beats
    if downbeats is not None:
        reference["downbeats"] = downbeats
    if reference:
        materialized["reference"] = reference

    return materialized


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

    results: list[dict[str, Any]] = []
    materialized_clips: list[dict[str, Any]] = []
    for clip in clips:
        entry: dict[str, Any] = {
            "id": clip["id"],
            "dataset": clip["dataset"],
            "status": "ok",
        }
        sliced_beats: list[float] | None = None
        sliced_downbeats: list[float] | None = None
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
                sliced_beats, sliced_downbeats = slice_beat_annotations(
                    beats,
                    downbeats,
                    start,
                    end,
                )
                ann_out = prepared_dir / f"{clip['id']}.beats.json"
                ann_out.write_text(
                    json.dumps({"beats": sliced_beats, "downbeats": sliced_downbeats})
                )
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

        materialized = _materialized_clip(
            clip,
            entry,
            beats=sliced_beats,
            downbeats=sliced_downbeats,
        )
        if materialized is not None:
            materialized_clips.append(materialized)
        results.append(entry)

    manifest_suffix = f"{corpus}-{dataset}" if dataset else corpus
    materialized_manifest = {
        "name": f"{manifest_suffix}_materialized",
        "description": (
            f"Evaluator-ready excerpts materialized from {corpus}. Only successful "
            "acquisition rows are included; source excerpt bounds remain provenance "
            "while audio/MIDI/beat timelines are rebased to zero. Full-piece MusicXML "
            "is omitted until excerpt-aligned score materialization exists."
        ),
        "source_corpus": corpus,
        "dataset_filter": dataset,
        "clips": materialized_clips,
    }
    manifest_out = cache.cache_dir() / f"manifest-{manifest_suffix}.json"
    manifest_out.write_text(json.dumps(materialized_manifest, indent=2) + "\n")

    report_out = cache.cache_dir() / f"prepared-{manifest_suffix}.json"
    summary = {
        "corpus": corpus,
        "dataset_filter": dataset,
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "manual": sum(1 for r in results if r["status"] == "manual"),
        "unsupported": sum(1 for r in results if r["status"] == "unsupported"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "materialized": len(materialized_clips),
        "materialized_manifest": str(manifest_out.resolve()),
        "acquisition_report": str(report_out.resolve()),
        "clips": results,
    }
    report_out.write_text(json.dumps(summary, indent=2) + "\n")
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

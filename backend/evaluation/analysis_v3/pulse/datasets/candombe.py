"""Build a held-out Candombe manifest for Beat This ``single_final*`` evaluation.

Beat This's default ``final*`` checkpoints trained on Candombe and therefore
must not be scored on this corpus as generalization evidence. The
``single_final*`` checkpoints instead use the published Beat This v1.0
``single.split`` files, where rows marked ``val`` are held out from training.

This helper selects only those validation rows. It never downloads or
redistributes audio; callers provide a local copy of the CC BY 4.0 dataset.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

ANNOTATION_SOURCE = "https://github.com/CPJKU/beat_this_annotations"
ANNOTATION_VERSION = "v1.0"
ANNOTATION_LICENSE = "MIT"
AUDIO_SOURCE = "https://doi.org/10.60895/redata/AY9CGZ"
AUDIO_LICENSE = "CC BY 4.0"
SOURCE_DATASET = "candombe"
EVALUATION_DATASET = "candombe_single_split_val"
SPLIT_PARTITION = "single_split_val"


def parse_candombe_beats(annotation_path: str | Path) -> dict[str, Any]:
    """Parse a Beat This Candombe ``.beats`` annotation file."""
    beats: list[float] = []
    downbeats: list[float] = []
    positions: list[int] = []

    with open(annotation_path) as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(
                    f"Malformed beat annotation at {annotation_path}:{line_number}: {line!r}"
                )
            beat_time = float(parts[0])
            beat_position = int(parts[1])
            beats.append(beat_time)
            positions.append(beat_position)
            if beat_position == 1:
                downbeats.append(beat_time)

    if not beats:
        raise ValueError(f"No beats found in {annotation_path}")
    if any(later <= earlier for earlier, later in zip(beats, beats[1:], strict=False)):
        raise ValueError(f"Beat times are not strictly increasing: {annotation_path}")

    intervals = np.diff(np.asarray(beats, dtype=float))
    positive_intervals = intervals[intervals > 0]
    reference_bpm = (
        float(60.0 / np.median(positive_intervals)) if positive_intervals.size else None
    )

    positive_positions = [position for position in positions if 0 < position <= 12]
    meter_numerator = max(positive_positions) if positive_positions else None
    return {
        "reference_beats": beats,
        "reference_downbeats": downbeats or None,
        "reference_beat_positions": positions,
        "reference_bpm": reference_bpm,
        "reference_bpm_method": "median_reference_interbeat_interval",
        "reference_meter_numerator": meter_numerator,
        "reference_meter_denominator": None,
    }


def parse_single_split(split_path: str | Path) -> dict[str, str]:
    """Parse Beat This ``single.split`` and return stem -> train/val."""
    assignments: dict[str, str] = {}
    with open(split_path) as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 2 or parts[1] not in {"train", "val"}:
                raise ValueError(f"Malformed split row at {split_path}:{line_number}: {line!r}")
            stem, partition = parts
            if stem in assignments:
                raise ValueError(f"Duplicate split assignment for {stem}")
            assignments[stem] = partition
    if not assignments:
        raise ValueError(f"No split assignments found in {split_path}")
    return assignments


def resolve_candombe_audio_path(audio_dir: str | Path, track_id: str) -> Path:
    """Resolve common layouts of the official Candombe FLAC archive."""
    audio_root = Path(audio_dir)
    filename = f"{track_id}.flac"
    candidates = (
        audio_root / filename,
        audio_root / "candombe_audio" / filename,
        audio_root / "audio" / filename,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def extract_candombe_single_val_manifest(
    annotation_dir: str,
    split_path: str,
    audio_dir: str,
    output_path: str,
) -> dict[str, Any]:
    """Create the exact Beat This v1.0 Candombe single-split validation manifest."""
    annotation_root = Path(annotation_dir)
    assignments = parse_single_split(split_path)
    validation_ids = sorted(stem for stem, partition in assignments.items() if partition == "val")
    if not validation_ids:
        raise ValueError("single split contains no Candombe validation rows")

    clips: list[dict[str, Any]] = []
    for track_id in validation_ids:
        annotation_path = annotation_root / f"{track_id}.beats"
        if not annotation_path.exists():
            raise FileNotFoundError(
                f"Missing Beat This v1.0 Candombe annotation for validation track: {annotation_path}"
            )
        audio_path = resolve_candombe_audio_path(audio_dir, track_id)
        clips.append(
            {
                "id": track_id,
                "audio_path": str(audio_path),
                "audio_available": audio_path.exists(),
                "dataset": EVALUATION_DATASET,
                "source_dataset": SOURCE_DATASET,
                "split_partition": SPLIT_PARTITION,
                "split_source": ANNOTATION_SOURCE,
                "split_version": ANNOTATION_VERSION,
                "annotation_source": ANNOTATION_SOURCE,
                "annotation_version": ANNOTATION_VERSION,
                "annotation_license": ANNOTATION_LICENSE,
                "audio_source": AUDIO_SOURCE,
                "audio_license": AUDIO_LICENSE,
                **parse_candombe_beats(annotation_path),
            }
        )

    manifest: dict[str, Any] = {
        "name": "candombe_beat_this_v1_single_split_val",
        "description": (
            "Candombe validation rows from Beat This annotations v1.0 single.split. "
            "Fair for Beat This single_final* checkpoints, not final*/small*."
        ),
        "dataset": EVALUATION_DATASET,
        "source_dataset": SOURCE_DATASET,
        "split_partition": SPLIT_PARTITION,
        "split_source": ANNOTATION_SOURCE,
        "split_version": ANNOTATION_VERSION,
        "annotation_source": ANNOTATION_SOURCE,
        "annotation_version": ANNOTATION_VERSION,
        "annotation_license": ANNOTATION_LICENSE,
        "audio_source": AUDIO_SOURCE,
        "audio_license": AUDIO_LICENSE,
        "audio_redistributed": False,
        "clips": clips,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Extracted {len(clips)} held-out Candombe clips to {output}")
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build held-out Candombe pulse manifest")
    parser.add_argument("annotation_dir")
    parser.add_argument("split_path")
    parser.add_argument("audio_dir")
    parser.add_argument("output_path")
    args = parser.parse_args()

    extract_candombe_single_val_manifest(
        args.annotation_dir,
        args.split_path,
        args.audio_dir,
        args.output_path,
    )

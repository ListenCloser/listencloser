"""Build a held-out GTZAN pulse manifest from Beat This v1.0 annotations.

The default Beat This ``final*`` checkpoints reserve GTZAN for testing, making
it a suitable in-paper held-out corpus for fair comparison. This helper does
not download or redistribute GTZAN audio; callers must provide a local copy.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ANNOTATION_SOURCE = "https://github.com/CPJKU/beat_this_annotations"
ANNOTATION_VERSION = "v1.0"
ANNOTATION_LICENSE = "MIT"
AUDIO_LICENSE = "unknown; user-supplied local GTZAN audio required"
_TRACK_RE = re.compile(r"^gtzan_(?P<genre>[a-z]+)_(?P<index>\d{5})$")


def parse_gtzan_beats(annotation_path: str | Path) -> dict[str, Any]:
    """Parse a Beat This GTZAN ``.beats`` annotation file."""
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

    if any(later <= earlier for earlier, later in zip(beats, beats[1:], strict=False)):
        raise ValueError(f"Beat times are not strictly increasing: {annotation_path}")

    reference_bpm = None
    if len(beats) >= 2:
        intervals = np.diff(np.asarray(beats, dtype=float))
        positive_intervals = intervals[intervals > 0]
        if positive_intervals.size:
            reference_bpm = float(60.0 / np.median(positive_intervals))

    meter_numerator = None
    positive_positions = [position for position in positions if position > 0]
    if positive_positions:
        candidate = max(positive_positions)
        if candidate <= 12:
            meter_numerator = candidate

    return {
        "reference_beats": beats,
        "reference_downbeats": downbeats or None,
        "reference_beat_positions": positions,
        "reference_bpm": reference_bpm,
        "reference_bpm_method": "median_reference_interbeat_interval",
        "reference_meter_numerator": meter_numerator,
        "reference_meter_denominator": None,
    }


def _parse_track_id(track_id: str) -> tuple[str, str]:
    match = _TRACK_RE.match(track_id)
    if not match:
        raise ValueError(f"Unexpected GTZAN annotation id: {track_id}")
    return match.group("genre"), match.group("index")


def resolve_gtzan_audio_path(audio_dir: str | Path, track_id: str) -> Path:
    """Resolve common GTZAN audio layouts without inventing an available file."""
    audio_root = Path(audio_dir)
    genre, index = _parse_track_id(track_id)
    original_name = f"{genre}.{index}.wav"
    candidates = (
        audio_root / "genres" / genre / original_name,
        audio_root / genre / original_name,
        audio_root / original_name,
        audio_root / f"{track_id}.wav",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def extract_gtzan_annotations(
    annotation_dir: str,
    audio_dir: str,
    output_path: str,
    *,
    max_per_genre: int | None = None,
) -> dict[str, Any]:
    """Create a deterministic GTZAN beat/downbeat manifest.

    ``annotation_dir`` should point at
    ``beat_this_annotations/gtzan/annotations/beats`` checked out at v1.0.
    Audio is never copied or downloaded; unresolved paths remain in the
    manifest and are reported as missing by the pulse runner.
    """
    annotation_root = Path(annotation_dir)
    per_genre_counts: dict[str, int] = defaultdict(int)
    clips: list[dict[str, Any]] = []

    for annotation_path in sorted(annotation_root.glob("*.beats")):
        track_id = annotation_path.stem
        genre, _ = _parse_track_id(track_id)
        if max_per_genre is not None and per_genre_counts[genre] >= max_per_genre:
            continue

        reference = parse_gtzan_beats(annotation_path)
        audio_path = resolve_gtzan_audio_path(audio_dir, track_id)
        clips.append(
            {
                "id": track_id,
                "audio_path": str(audio_path),
                "audio_available": audio_path.exists(),
                "dataset": "gtzan",
                "genre": genre,
                "annotation_source": ANNOTATION_SOURCE,
                "annotation_version": ANNOTATION_VERSION,
                "annotation_license": ANNOTATION_LICENSE,
                "audio_license": AUDIO_LICENSE,
                **reference,
            }
        )
        per_genre_counts[genre] += 1

    manifest: dict[str, Any] = {
        "name": "gtzan_beat_this_v1_held_out",
        "description": (
            "GTZAN beat/downbeat annotations from Beat This annotations v1.0. "
            "GTZAN is held out from Beat This final*/small* training."
        ),
        "dataset": "gtzan",
        "annotation_source": ANNOTATION_SOURCE,
        "annotation_version": ANNOTATION_VERSION,
        "annotation_license": ANNOTATION_LICENSE,
        "audio_license": AUDIO_LICENSE,
        "audio_redistributed": False,
        "clips": clips,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Extracted {len(clips)} GTZAN clips to {output}")
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a GTZAN pulse manifest")
    parser.add_argument("annotation_dir")
    parser.add_argument("audio_dir")
    parser.add_argument("output_path")
    parser.add_argument("--max-per-genre", type=int, default=None)
    args = parser.parse_args()

    extract_gtzan_annotations(
        args.annotation_dir,
        args.audio_dir,
        args.output_path,
        max_per_genre=args.max_per_genre,
    )

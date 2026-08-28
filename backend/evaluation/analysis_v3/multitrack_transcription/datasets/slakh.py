"""Slakh2100-redux manifest utilities for multi-instrument AMT evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_root(dataset_root: Path, split: str) -> Path:
    candidate = dataset_root / split
    return candidate if candidate.is_dir() else dataset_root


def build_slakh_manifest(
    dataset_root: Path,
    *,
    split: str = "test",
    limit: int = 10,
    hash_files: bool = False,
) -> dict[str, Any]:
    """Build a deterministic manifest from an unpacked Slakh2100-redux tree.

    Reference MIDI uses the per-source ``MIDI/SXX.mid`` files because those are
    the exact MIDI tracks used to synthesize the corresponding stems. The
    original ``all_src.mid`` is intentionally not used as ground truth.
    """

    root = _split_root(dataset_root, split)
    tracks: list[dict[str, Any]] = []
    for track_dir in sorted(root.glob("Track*")):
        mix_path = track_dir / "mix.flac"
        midi_paths = sorted((track_dir / "MIDI").glob("*.mid"))
        if not mix_path.is_file() or not midi_paths:
            continue
        item = {
            "id": track_dir.name,
            "mix": str(mix_path.relative_to(dataset_root)),
            "reference_midis": [str(path.relative_to(dataset_root)) for path in midi_paths],
            "mix_bytes": mix_path.stat().st_size,
            "reference_midi_count": len(midi_paths),
        }
        if hash_files:
            item["mix_sha256"] = _sha256(mix_path)
            item["reference_midi_sha256"] = {
                str(path.relative_to(dataset_root)): _sha256(path) for path in midi_paths
            }
        tracks.append(item)
        if len(tracks) >= limit:
            break

    if not tracks:
        raise ValueError(f"no Slakh tracks found under {root}")
    return {
        "name": "slakh2100-redux-multitrack",
        "split": split,
        "selection": "lexicographically first valid tracks",
        "limit": limit,
        "dataset_license": "CC BY 4.0",
        "dataset_source": "https://zenodo.org/records/4599666",
        "ground_truth": (
            "per-source MIDI/SXX.mid files; these are the MIDI files used to synthesize "
            "the corresponding Slakh stems"
        ),
        "entries": tracks,
    }


def write_manifest(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")

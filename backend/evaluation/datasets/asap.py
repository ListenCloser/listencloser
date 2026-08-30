"""ASAP dataset adapter (real piano performance ↔ aligned score).

Source:   https://github.com/fosfrancesco/asap-dataset
Version:  repository snapshot (performance MIDI + score MIDI + MusicXML)
License:  CC BY-NC-SA 4.0 (as stated in the repository README)
Split:    subset of published pieces (no official train/test split)

ASAP links performance audio/notes to aligned beat/downbeat annotations and
score-derived MusicXML. Audio is reconstructed from MAESTRO by ASAP's
``initialize_dataset.py`` and the exact file correspondences are recorded in
``metadata.csv``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from evaluation.datasets import cache
from evaluation.datasets.registry import DatasetAdapter, ManualAcquisitionError, ResolvedClip


def _normalize_relative_path(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./")


def find_performance_entry(metadata_path: Path, source_id: str) -> dict[str, str] | None:
    """Return the ASAP metadata row for an exact ``midi_performance`` path."""
    wanted = _normalize_relative_path(source_id)
    with metadata_path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            candidate = _normalize_relative_path(row.get("midi_performance", ""))
            if candidate == wanted:
                return {key: value or "" for key, value in row.items() if key is not None}
    return None


def _dataset_path(dataset_dir: Path, relative: str, *, field: str) -> Path:
    """Resolve one metadata path without allowing it to escape the dataset root."""
    if not relative:
        raise ManualAcquisitionError(f"ASAP metadata is missing required field '{field}'.")
    root = dataset_dir.resolve()
    path = (dataset_dir / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ManualAcquisitionError(
            f"ASAP metadata field '{field}' points outside the dataset directory: {relative}"
        ) from exc
    return path


class AsapAdapter(DatasetAdapter):
    name = "asap"
    license = "CC BY-NC-SA 4.0"

    def resolve(self, clip: dict[str, Any]) -> ResolvedClip:
        ddir = cache.dataset_dir("asap")
        metadata_path = ddir / "metadata.csv"
        if not metadata_path.exists():
            raise ManualAcquisitionError(
                "ASAP requires manual acquisition. Clone the ASAP dataset into "
                "MUSIC_EVAL_CACHE_DIR/asap, download MAESTRO as instructed upstream, "
                "and run ASAP's initialize_dataset.py. Missing: " + str(metadata_path)
            )

        source_id = str(clip["source_id"])
        entry = find_performance_entry(metadata_path, source_id)
        if entry is None:
            raise ManualAcquisitionError(
                "ASAP source_id must exactly match metadata.csv midi_performance. "
                f"No row found for: {source_id}"
            )

        midi_path = _dataset_path(
            ddir,
            entry.get("midi_performance", ""),
            field="midi_performance",
        )
        audio_path = _dataset_path(
            ddir,
            entry.get("audio_performance", ""),
            field="audio_performance",
        )
        xml_path = _dataset_path(ddir, entry.get("xml_score", ""), field="xml_score")
        beats_path = _dataset_path(
            ddir,
            entry.get("performance_annotations", ""),
            field="performance_annotations",
        )

        missing = [str(path) for path in (audio_path, midi_path) if not path.exists()]
        if missing:
            raise ManualAcquisitionError(
                "ASAP files are not fully materialized. Run the upstream initialization "
                "workflow before evaluation. Missing: " + ", ".join(missing)
            )

        return ResolvedClip(
            audio_path=str(audio_path),
            reference_midi_path=str(midi_path),
            reference_musicxml_path=str(xml_path) if xml_path.exists() else None,
            beats_path=str(beats_path) if beats_path.exists() else None,
        )

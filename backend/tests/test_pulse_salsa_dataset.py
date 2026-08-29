from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from evaluation.analysis_v3.pulse.datasets.salsa import (
    DATASET,
    _align_reference_to_fragment,
    build_salsa_manifest,
    parse_salsa_beats,
)


def test_parse_salsa_beats_converts_published_milliseconds(tmp_path: Path) -> None:
    path = tmp_path / "73.txt"
    path.write_text("500\n1000\n1500\n")

    assert parse_salsa_beats(path) == [0.5, 1.0, 1.5]


def test_fragment_alignment_refuses_unproven_truncation() -> None:
    with pytest.raises(ValueError, match="Refusing to truncate or guess"):
        _align_reference_to_fragment(
            [0.5, 1.0, 1.5, 40.0],
            duration_seconds=30.0,
            metadata_row={},
        )


def test_fragment_alignment_accepts_explicit_upstream_offset() -> None:
    beats, provenance = _align_reference_to_fragment(
        [9.5, 10.5, 11.5, 12.5, 13.5],
        duration_seconds=3.0,
        metadata_row={"fragment_start_seconds": "10.0"},
    )

    assert beats == [0.5, 1.5, 2.5]
    assert provenance == {
        "fragment_alignment": "explicit_metadata_offset",
        "fragment_offset_seconds": 10.0,
    }


def test_build_salsa_manifest_joins_ids_and_records_independent_dataset(tmp_path: Path) -> None:
    audio_root = tmp_path / "audio"
    annotation_root = tmp_path / "beats"
    audio_root.mkdir()
    annotation_root.mkdir()

    sample_rate = 8000
    sf.write(audio_root / "73.wav", np.zeros(sample_rate * 2, dtype=np.float32), sample_rate)
    (annotation_root / "73.txt").write_text("250\n750\n1250\n1750\n")

    metadata_path = tmp_path / "songs.csv"
    with metadata_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["song ID", "song title"])
        writer.writeheader()
        writer.writerow({"song ID": "73", "song title": "fixture"})

    output = tmp_path / "manifest.json"
    manifest = build_salsa_manifest(audio_root, annotation_root, metadata_path, output)

    assert manifest["dataset"] == DATASET
    assert manifest["audio_redistributed"] is False
    assert len(manifest["clips"]) == 1
    clip = manifest["clips"][0]
    assert clip["id"] == "salsa_73"
    assert clip["reference_beats"] == [0.25, 0.75, 1.25, 1.75]
    assert clip["fragment_alignment"] == "annotation_timeline_fits_fragment"
    assert clip["reference_downbeats"] is None

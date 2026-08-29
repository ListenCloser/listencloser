"""Tests for the held-out GTZAN pulse manifest builder."""

from __future__ import annotations

import json

import pytest
from backend.evaluation.analysis_v3.pulse.datasets.gtzan import (
    extract_gtzan_annotations,
    parse_gtzan_beats,
    resolve_gtzan_audio_path,
)


def test_parse_gtzan_beats_extracts_downbeats_tempo_and_meter(tmp_path):
    annotation = tmp_path / "gtzan_blues_00000.beats"
    annotation.write_text("0.0\t1\n0.5\t2\n1.0\t3\n1.5\t4\n2.0\t1\n")

    result = parse_gtzan_beats(annotation)

    assert result["reference_beats"] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert result["reference_downbeats"] == [0.0, 2.0]
    assert result["reference_beat_positions"] == [1, 2, 3, 4, 1]
    assert result["reference_bpm"] == pytest.approx(120.0)
    assert result["reference_meter_numerator"] == 4
    assert result["reference_meter_denominator"] is None


def test_parse_gtzan_beats_rejects_non_monotonic_annotations(tmp_path):
    annotation = tmp_path / "gtzan_blues_00000.beats"
    annotation.write_text("0.5\t1\n0.5\t2\n")

    with pytest.raises(ValueError, match="strictly increasing"):
        parse_gtzan_beats(annotation)


def test_resolve_gtzan_audio_path_supports_original_layout(tmp_path):
    audio = tmp_path / "genres" / "blues" / "blues.00000.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"not-real-audio")

    resolved = resolve_gtzan_audio_path(tmp_path, "gtzan_blues_00000")

    assert resolved == audio


def test_extract_gtzan_manifest_is_deterministic_and_does_not_redistribute_audio(
    tmp_path,
):
    annotations = tmp_path / "annotations"
    annotations.mkdir()
    (annotations / "gtzan_blues_00000.beats").write_text(
        "0.0\t1\n0.5\t2\n1.0\t3\n1.5\t4\n"
    )
    (annotations / "gtzan_blues_00001.beats").write_text(
        "0.0\t1\n0.6\t2\n1.2\t3\n1.8\t4\n"
    )
    (annotations / "gtzan_jazz_00000.beats").write_text(
        "0.0\t1\n0.4\t2\n0.8\t3\n1.2\t4\n"
    )
    output = tmp_path / "gtzan.json"

    manifest = extract_gtzan_annotations(
        str(annotations),
        str(tmp_path / "audio"),
        str(output),
        max_per_genre=1,
    )

    assert [clip["id"] for clip in manifest["clips"]] == [
        "gtzan_blues_00000",
        "gtzan_jazz_00000",
    ]
    assert manifest["dataset"] == "gtzan"
    assert manifest["annotation_version"] == "v1.0"
    assert manifest["annotation_license"] == "MIT"
    assert manifest["audio_redistributed"] is False
    assert all(clip["audio_available"] is False for clip in manifest["clips"])
    assert json.loads(output.read_text()) == manifest

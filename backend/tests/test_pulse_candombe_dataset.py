"""Tests for the Beat This Candombe single-split validation manifest."""

from __future__ import annotations

import json

import pytest
from backend.evaluation.analysis_v3.pulse.datasets.candombe import (
    EVALUATION_DATASET,
    extract_candombe_single_val_manifest,
    parse_candombe_beats,
    parse_single_split,
    resolve_candombe_audio_path,
)


def test_parse_candombe_beats_extracts_downbeats_tempo_and_meter(tmp_path):
    annotation = tmp_path / "piece.beats"
    annotation.write_text("0.0\t1\n0.5\t2\n1.0\t3\n1.5\t4\n2.0\t1\n")

    result = parse_candombe_beats(annotation)

    assert result["reference_beats"] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert result["reference_downbeats"] == [0.0, 2.0]
    assert result["reference_bpm"] == pytest.approx(120.0)
    assert result["reference_meter_numerator"] == 4


def test_parse_single_split_preserves_exact_train_val_assignments(tmp_path):
    split = tmp_path / "single.split"
    split.write_text("a\ttrain\nb\tval\n")

    assert parse_single_split(split) == {"a": "train", "b": "val"}


def test_parse_single_split_rejects_unknown_partition(tmp_path):
    split = tmp_path / "single.split"
    split.write_text("a\ttest\n")

    with pytest.raises(ValueError, match="Malformed split row"):
        parse_single_split(split)


def test_resolve_candombe_audio_path_supports_official_archive_layout(tmp_path):
    audio = tmp_path / "candombe_audio" / "piece.flac"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"not-real-audio")

    assert resolve_candombe_audio_path(tmp_path, "piece") == audio


def test_manifest_contains_only_single_split_validation_rows(tmp_path):
    annotations = tmp_path / "annotations"
    annotations.mkdir()
    for stem in ("train_piece", "val_b", "val_a"):
        (annotations / f"{stem}.beats").write_text("0.0\t1\n0.5\t2\n1.0\t3\n1.5\t4\n")
    split = tmp_path / "single.split"
    split.write_text("train_piece\ttrain\nval_b\tval\nval_a\tval\n")
    output = tmp_path / "manifest.json"

    manifest = extract_candombe_single_val_manifest(
        str(annotations),
        str(split),
        str(tmp_path / "audio"),
        str(output),
    )

    assert [clip["id"] for clip in manifest["clips"]] == ["val_a", "val_b"]
    assert manifest["dataset"] == EVALUATION_DATASET
    assert manifest["source_dataset"] == "candombe"
    assert manifest["split_partition"] == "single_split_val"
    assert manifest["split_version"] == "v1.0"
    assert manifest["audio_license"] == "CC BY 4.0"
    assert manifest["audio_redistributed"] is False
    assert all(clip["dataset"] == EVALUATION_DATASET for clip in manifest["clips"])
    assert all(clip["audio_available"] is False for clip in manifest["clips"])
    assert json.loads(output.read_text()) == manifest


def test_manifest_fails_if_a_validation_annotation_is_missing(tmp_path):
    annotations = tmp_path / "annotations"
    annotations.mkdir()
    split = tmp_path / "single.split"
    split.write_text("missing_piece\tval\n")

    with pytest.raises(FileNotFoundError, match="validation track"):
        extract_candombe_single_val_manifest(
            str(annotations),
            str(split),
            str(tmp_path / "audio"),
            str(tmp_path / "manifest.json"),
        )

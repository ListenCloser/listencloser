"""Regression coverage for ASAP corpus provenance and annotation parsing."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from evaluation.datasets.asap import AsapAdapter
from evaluation.datasets.prepare import _read_beat_annotations
from evaluation.datasets.registry import ManualAcquisitionError


def _write_metadata(path: Path, row: dict[str, str]) -> None:
    fields = [
        "composer",
        "title",
        "folder",
        "xml_score",
        "midi_score",
        "midi_performance",
        "performance_annotations",
        "midi_score_annotations",
        "maestro_midi_performance",
        "maestro_audio_performance",
        "start",
        "end",
        "audio_performance",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)


def test_asap_adapter_resolves_exact_metadata_correspondences(monkeypatch, tmp_path):
    monkeypatch.setenv("MUSIC_EVAL_CACHE_DIR", str(tmp_path))
    ddir = tmp_path / "asap"
    ddir.mkdir()

    source_id = "Chopin/Ballades/1/BuiJL04M.mid"
    midi_rel = source_id
    audio_rel = "Chopin/Ballades/1/BuiJL04M.wav"
    xml_rel = "Chopin/Ballades/1/xml_score.musicxml"
    annotations_rel = "Chopin/Ballades/1/BuiJL04M_annotations.txt"

    for relative, payload in (
        (midi_rel, b"midi"),
        (audio_rel, b"audio"),
        (xml_rel, b"<score-partwise/>"),
        (annotations_rel, b"0\t0\tdb\n"),
    ):
        target = ddir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    _write_metadata(
        ddir / "metadata.csv",
        {
            "composer": "Chopin",
            "title": "Ballades_1",
            "folder": "Chopin/Ballades/1",
            "xml_score": xml_rel,
            "midi_score": "Chopin/Ballades/1/midi_score.mid",
            "midi_performance": midi_rel,
            "performance_annotations": annotations_rel,
            "audio_performance": audio_rel,
        },
    )

    resolved = AsapAdapter().resolve({"source_id": source_id, "dataset": "asap"})

    assert resolved.reference_midi_path == str(ddir / midi_rel)
    assert resolved.audio_path == str(ddir / audio_rel)
    assert resolved.reference_musicxml_path == str(ddir / xml_rel)
    assert resolved.beats_path == str(ddir / annotations_rel)


def test_asap_adapter_rejects_placeholder_source_id(monkeypatch, tmp_path):
    monkeypatch.setenv("MUSIC_EVAL_CACHE_DIR", str(tmp_path))
    ddir = tmp_path / "asap"
    ddir.mkdir()
    _write_metadata(
        ddir / "metadata.csv",
        {
            "composer": "Bach",
            "title": "Fugue_bwv_846",
            "midi_performance": "Bach/Fugue/bwv_846/Shi05M.mid",
        },
    )

    with pytest.raises(ManualAcquisitionError, match="exactly match metadata.csv"):
        AsapAdapter().resolve({"source_id": "Bach/01", "dataset": "asap"})


def test_asap_annotation_parser_uses_timestamp_and_preserves_downbeats(tmp_path):
    annotations = tmp_path / "performance_annotations.txt"
    annotations.write_text(
        "0.000\t0.000\tdb,4/4\n"
        "0.500\t0.500\tb\n"
        "1.000\t1.000\tbR\n"
        "1.500\t1.500\t0\n"
        "2.000\t2.000\t3/4\n"
    )

    beats, downbeats = _read_beat_annotations(str(annotations))

    assert beats == [0.0, 0.5, 1.0]
    assert downbeats == [0.0]


def test_real_world_asap_rows_pin_real_performance_midi_paths():
    manifest_path = (
        Path(__file__).resolve().parents[1] / "evaluation" / "corpora" / "real_world_v1.json"
    )
    data = json.loads(manifest_path.read_text())
    asap_rows = [clip for clip in data["clips"] if clip["dataset"] == "asap"]

    assert len(asap_rows) == 5
    assert {clip["source_id"] for clip in asap_rows} == {
        "Bach/Fugue/bwv_846/Shi05M.mid",
        "Chopin/Ballades/1/BuiJL04M.mid",
        "Mozart/Fantasie_475/Huangci05M.mid",
        "Scriabin/Etudes_op_8/11/Shi08M.mid",
        "Schubert/Impromptu_op.90_D.899/1/Duepree08M.mid",
    }

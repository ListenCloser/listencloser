"""Contracts for evaluator-ready manifests emitted by corpus preparation."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation import models
from evaluation.datasets import prepare
from evaluation.datasets.registry import ManualAcquisitionError, ResolvedClip


def test_prepare_corpus_separates_acquisition_status_from_eval_manifest(monkeypatch, tmp_path):
    source_manifest = tmp_path / "source.json"
    source_manifest.write_text(
        json.dumps(
            {
                "name": "fixture",
                "clips": [
                    {
                        "id": "ready",
                        "dataset": "asap",
                        "category": "solo_piano",
                        "split": "curated",
                        "source_id": "Composer/Piece/Performance.mid",
                        "license": "CC BY-NC-SA 4.0",
                        "metrics": ["note_onset", "beat", "downbeat", "notation"],
                        "excerpt_start": 10.0,
                        "excerpt_end": 11.0,
                        "reference": {
                            "bpm": 120,
                            "beats": [10.25],
                            "downbeats": [10.25],
                            "chords": [{"start": 10.0, "end": 11.0, "root": "C"}],
                            "sections": [{"start": 10.0, "end": 11.0, "label": "A"}],
                        },
                    },
                    {
                        "id": "manual",
                        "dataset": "asap",
                        "category": "solo_piano",
                        "source_id": "Composer/Other/Performance.mid",
                        "license": "CC BY-NC-SA 4.0",
                        "excerpt_start": 0.0,
                        "excerpt_end": 1.0,
                    },
                ],
            }
        )
    )

    audio = tmp_path / "source.wav"
    audio.write_bytes(b"source-audio")
    midi = tmp_path / "performance.mid"
    midi.write_bytes(b"source-midi")
    musicxml = tmp_path / "full-piece.musicxml"
    musicxml.write_text("<score-partwise/>")
    annotations = tmp_path / "performance_annotations.txt"
    annotations.write_text("10.0\t10.0\tdb,4/4\n10.5\t10.5\tb\n")

    monkeypatch.setattr(prepare, "_manifest_path", lambda _name: source_manifest)
    monkeypatch.setattr(prepare.cache, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(prepare, "slice_audio", lambda _data, _start, _end: b"rebased-audio")
    monkeypatch.setattr(
        prepare,
        "slice_midi",
        lambda _data, _start, _end: (b"rebased-midi", [{"pitch": 60}]),
    )

    def fake_resolve(clip):
        if clip["id"] == "manual":
            raise ManualAcquisitionError("fixture requires manual acquisition")
        return ResolvedClip(
            audio_path=str(audio),
            reference_midi_path=str(midi),
            reference_musicxml_path=str(musicxml),
            beats_path=str(annotations),
        )

    monkeypatch.setattr(prepare, "resolve_clip", fake_resolve)

    summary = prepare.prepare_corpus("fixture")

    assert summary["total"] == 2
    assert summary["ok"] == 1
    assert summary["manual"] == 1
    assert summary["materialized"] == 1
    assert [row["status"] for row in summary["clips"]] == ["ok", "manual"]
    assert Path(summary["acquisition_report"]).name == "prepared-fixture.json"

    manifest_path = Path(summary["materialized_manifest"])
    payload = json.loads(manifest_path.read_text())
    assert payload["name"] == "fixture_materialized"
    assert len(payload["clips"]) == 1

    row = payload["clips"][0]
    assert row["id"] == "ready"
    assert row["category"] == "solo_piano"
    assert row["dataset"] == "asap"
    assert row["split"] == "curated"
    assert row["source_id"] == "Composer/Piece/Performance.mid"
    assert row["license"] == "CC BY-NC-SA 4.0"
    assert row["metrics"] == ["note_onset", "beat", "downbeat", "notation"]
    assert row["excerpt_start"] == 10.0
    assert row["excerpt_end"] == 11.0
    assert row["reference"] == {
        "bpm": 120,
        "beats": [0.0, 0.5],
        "downbeats": [0.0],
    }
    assert "chords" not in row["reference"]
    assert "sections" not in row["reference"]
    assert "reference_musicxml" not in row

    assert Path(row["audio"]).read_bytes() == b"rebased-audio"
    assert Path(row["reference_midi"]).read_bytes() == b"rebased-midi"

    loaded = models.CorpusManifest.from_file(str(manifest_path))
    assert len(loaded.clips) == 1
    assert loaded.clips[0].source_id == "Composer/Piece/Performance.mid"
    assert loaded.clips[0].reference.bpm == 120
    assert loaded.clips[0].reference.beats == [0.0, 0.5]
    assert loaded.clips[0].reference.downbeats == [0.0]
    assert loaded.clips[0].reference_musicxml is None

    full_report_path = Path(summary["acquisition_report"])
    full_report_before = full_report_path.read_text()
    filtered = prepare.prepare_corpus("fixture", dataset="asap")

    assert Path(filtered["acquisition_report"]).name == "prepared-fixture-asap.json"
    assert Path(filtered["materialized_manifest"]).name == "manifest-fixture-asap.json"
    assert full_report_path.read_text() == full_report_before

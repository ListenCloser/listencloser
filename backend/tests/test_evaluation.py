"""Unit tests for evaluation metrics."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from evaluation.analysis_metrics import compute_analysis_metrics
from evaluation.beat_metrics import compute_beat_metrics
from evaluation.corpus import build_piano_synthetic_fixture, validate_clip_fixtures
from evaluation.models import CorpusManifest, Reference
from evaluation.notation_metrics import diagnose_musicxml
from evaluation.transcription_metrics import (
    Note,
    compute_note_metrics,
)


class TestTranscriptionMetrics:
    def test_perfect_match(self):
        pred = [Note(60, 0.0, 0.5, 64), Note(64, 0.5, 1.0, 64)]
        ref = [Note(60, 0.0, 0.5, 64), Note(64, 0.5, 1.0, 64)]
        m = compute_note_metrics(pred, ref)
        assert m.note_f1 == 1.0
        assert m.onset_f1 == 1.0
        assert m.matched_count == 2
        assert m.excessive_count == 0
        assert m.missed_count == 0

    def test_no_predictions(self):
        m = compute_note_metrics([], [Note(60, 0.0, 0.5, 64)])
        assert m.note_precision == 0.0
        assert m.note_recall == 0.0
        assert m.note_f1 == 0.0
        assert m.predicted_count == 0
        assert m.reference_count == 1

    def test_no_references(self):
        m = compute_note_metrics([Note(60, 0.0, 0.5, 64)], [])
        assert m.note_precision == 0.0
        assert m.note_recall == 0.0
        assert m.note_f1 == 0.0

    def test_duplicate_predictions(self):
        pred = [Note(60, 0.0, 0.5, 64), Note(60, 0.0, 0.5, 64)]
        ref = [Note(60, 0.0, 0.5, 64)]
        m = compute_note_metrics(pred, ref)
        assert m.matched_count == 1
        assert m.excessive_count == 1

    def test_onset_within_tolerance(self):
        pred = [Note(60, 0.03, 0.5, 64)]
        ref = [Note(60, 0.0, 0.5, 64)]
        m = compute_note_metrics(pred, ref, onset_tolerance=0.05)
        assert m.onset_f1 == 1.0

    def test_onset_outside_tolerance(self):
        pred = [Note(60, 0.10, 0.5, 64)]
        ref = [Note(60, 0.0, 0.5, 64)]
        m = compute_note_metrics(pred, ref, onset_tolerance=0.05)
        assert m.note_f1 == 0.0

    def test_wrong_pitch_no_match(self):
        pred = [Note(61, 0.0, 0.5, 64)]
        ref = [Note(60, 0.0, 0.5, 64)]
        m = compute_note_metrics(pred, ref)
        assert m.note_f1 == 0.0

    def test_onset_f1_differs_from_note_f1_when_offsets_differ(self):
        # Same onset + pitch, but the predicted note is much shorter.
        pred = [Note(60, 0.0, 0.2, 64)]
        ref = [Note(60, 0.0, 1.0, 64)]
        m = compute_note_metrics(pred, ref, onset_tolerance=0.05, offset_tolerance=0.05)
        assert m.onset_f1 == 1.0  # onset-only match succeeds
        assert m.note_f1 == 0.0  # offset mismatch fails strict note match
        assert m.onset_matched_count == 1
        assert m.matched_count == 0

    def test_note_f1_equals_onset_f1_when_offsets_match(self):
        pred = [Note(60, 0.0, 1.0, 64)]
        ref = [Note(60, 0.0, 1.0, 64)]
        m = compute_note_metrics(pred, ref)
        assert m.note_f1 == 1.0
        assert m.onset_f1 == 1.0


class TestBeatMetrics:
    def test_bpm_error(self):
        m = compute_beat_metrics(
            predicted_beats=[],
            predicted_bpm=125.0,
            predicted_downbeats=[],
            reference_beats=[],
            reference_bpm=120.0,
            reference_downbeats=[],
        )
        assert m.bpm_absolute_error == 5.0
        assert m.bpm_relative_error_pct == pytest.approx(4.17, rel=0.1)

    def test_beat_match(self):
        m = compute_beat_metrics(
            predicted_beats=[0.0, 0.5, 1.0],
            predicted_bpm=None,
            predicted_downbeats=None,
            reference_beats=[0.0, 0.5, 1.0],
            reference_bpm=None,
            reference_downbeats=None,
            tolerance=0.07,
        )
        assert m.beat_f1 == 1.0
        assert m.matched_beat_count == 3

    def test_no_reference_returns_none(self):
        m = compute_beat_metrics(None, None, None, None, None, None)
        assert m.beat_f1 is None
        assert m.bpm_absolute_error is None


class TestNotationMetrics:
    def test_valid_musicxml(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE score-partwise PUBLIC>
        <score-partwise><part-list/><part id="P1"><measure number="1">
        <attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note>
        </measure></part></score-partwise>"""
        d = diagnose_musicxml(xml)
        assert d.parse_valid
        assert d.total_note_count == 1
        assert d.measure_count == 1

    def test_invalid_xml(self):
        d = diagnose_musicxml(b"not musicxml at all")
        assert not d.parse_valid
        assert len(d.issues) > 0


class TestAnalysisMetrics:
    def test_key_correct(self):
        ref = Reference(key="C major")
        m = compute_analysis_metrics("C major", None, None, None, None, ref)
        assert m.key_correct is True

    def test_key_wrong(self):
        ref = Reference(key="C major")
        m = compute_analysis_metrics("A minor", None, None, None, None, ref)
        assert m.key_correct is False

    def test_no_reference_returns_none(self):
        ref = Reference()
        m = compute_analysis_metrics("C major", 120.0, "4/4", [], [], ref)
        assert m.key_correct is None
        assert m.bpm_absolute_error is None


class TestCorpus:
    def test_manifest_loading(self):
        data = {
            "name": "test",
            "description": "test corpus",
            "clips": [
                {
                    "id": "test1",
                    "audio": "test.wav",
                    "category": "solo_piano",
                    "reference": {"bpm": 120},
                }
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            manifest = CorpusManifest.from_file(f.name)
            assert manifest.name == "test"
            assert len(manifest.clips) == 1
            c = manifest.clips[0]
            assert c.id == "test1"
            assert c.reference.bpm == 120
        os.unlink(f.name)

    def test_build_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            build_piano_synthetic_fixture(d)
            manifest_path = os.path.join(d, "manifest.json")
            assert os.path.isfile(manifest_path)
            assert os.path.isfile(os.path.join(d, "piano-synthetic.wav"))
            assert os.path.isfile(os.path.join(d, "piano-synthetic.mid"))
            manifest = CorpusManifest.from_file(manifest_path)
            assert len(manifest.clips) == 1
            issues = validate_clip_fixtures(manifest.clips[0])
            assert not issues

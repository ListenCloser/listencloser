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
from evaluation.transcription_metrics import Note, compute_note_metrics


class TestTranscriptionMetrics:
    def test_perfect_match(self):
        pred = [Note(60, 0.0, 0.5, 64), Note(64, 0.5, 1.0, 64)]
        ref = [Note(60, 0.0, 0.5, 64), Note(64, 0.5, 1.0, 64)]
        m = compute_note_metrics(pred, ref)
        assert m.onset_note_f1 == 1.0
        assert m.onset_offset_note_f1 == 1.0
        assert m.onset_matched_count == 2
        assert m.onset_offset_matched_count == 2
        assert m.excessive_count == 0
        assert m.missed_count == 0

    def test_no_predictions(self):
        m = compute_note_metrics([], [Note(60, 0.0, 0.5, 64)])
        assert m.onset_note_precision == 0.0
        assert m.onset_note_recall == 0.0
        assert m.onset_note_f1 == 0.0
        assert m.predicted_count == 0
        assert m.reference_count == 1

    def test_no_references(self):
        m = compute_note_metrics([Note(60, 0.0, 0.5, 64)], [])
        assert m.onset_note_precision == 0.0
        assert m.onset_note_recall == 0.0
        assert m.onset_note_f1 == 0.0

    def test_duplicate_predictions(self):
        pred = [Note(60, 0.0, 0.5, 64), Note(60, 0.0, 0.5, 64)]
        ref = [Note(60, 0.0, 0.5, 64)]
        m = compute_note_metrics(pred, ref)
        assert m.onset_matched_count == 1
        assert m.excessive_count == 1

    def test_onset_within_tolerance(self):
        pred = [Note(60, 0.03, 0.5, 64)]
        ref = [Note(60, 0.0, 0.5, 64)]
        m = compute_note_metrics(pred, ref, onset_tolerance=0.05)
        assert m.onset_note_f1 == 1.0

    def test_onset_outside_tolerance(self):
        pred = [Note(60, 0.10, 0.5, 64)]
        ref = [Note(60, 0.0, 0.5, 64)]
        m = compute_note_metrics(pred, ref, onset_tolerance=0.05)
        assert m.onset_note_f1 == 0.0

    def test_wrong_pitch_no_match(self):
        pred = [Note(61, 0.0, 0.5, 64)]
        ref = [Note(60, 0.0, 0.5, 64)]
        m = compute_note_metrics(pred, ref)
        assert m.onset_note_f1 == 0.0

    def test_onset_offset_separate_from_onset_only(self):
        """Onset-offset F1 should differ from onset-only when durations differ."""
        pred = [Note(60, 0.0, 0.5, 64)]
        ref = [Note(60, 0.0, 0.8, 64)]
        m = compute_note_metrics(pred, ref, offset_tolerance=0.05)
        assert m.onset_note_f1 == 1.0  # onset match
        assert m.onset_offset_note_f1 == 0.0  # offset mismatch
        assert m.onset_matched_count == 1
        assert m.onset_offset_matched_count == 0

    def test_note_with_different_duration_same_onset(self):
        """Matched notes with different durations still count as onset matches."""
        pred = [
            Note(60, 0.0, 0.3, 64),
            Note(64, 0.5, 0.7, 64),
        ]
        ref = [
            Note(60, 0.0, 0.5, 64),
            Note(64, 0.5, 1.0, 64),
        ]
        m = compute_note_metrics(pred, ref, offset_tolerance=0.3)
        assert m.onset_note_f1 == 1.0
        assert m.onset_offset_note_f1 == 1.0
        assert m.onset_offset_matched_count == 2

    def test_non_120_bpm_midi_handling(self):
        """Notes at 90 BPM should still match when timing is in real seconds."""
        pred = [Note(60, 0.0, 0.667, 64)]
        ref = [Note(60, 0.0, 0.667, 64)]
        m = compute_note_metrics(pred, ref, onset_tolerance=0.05, offset_tolerance=0.05)
        assert m.onset_note_f1 == 1.0
        assert m.onset_offset_note_f1 == 1.0


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

    def test_unmatched_reference_is_empty(self):
        """When a reference beat has no match, it should NOT be silently kept."""
        from evaluation.beat_metrics import _match_timestamps

        matched, unmatched_pred, unmatched_ref = _match_timestamps(
            [0.0, 1.0], [0.0, 0.5, 1.0], tolerance=0.07
        )
        assert matched == 2  # 0.0 and 1.0 match
        assert len(unmatched_pred) == 0
        assert len(unmatched_ref) == 1  # 0.5 has no good match


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

    def test_non_default_divisions(self):
        """Notes with divisions=8 should still get correct note count."""
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE score-partwise PUBLIC>
        <score-partwise><part-list/><part id="P1"><measure number="1">
        <attributes><divisions>8</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>8</duration></note>
        <note><pitch><step>D</step><octave>4</octave></pitch><duration>8</duration></note>
        </measure></part></score-partwise>"""
        d = diagnose_musicxml(xml)
        assert d.parse_valid
        assert d.total_note_count == 2
        assert d.measure_count == 1


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

    def test_chord_one_to_one_no_overcount(self):
        """One prediction should not match multiple references."""
        ref = Reference(chords=[{"root": "C", "start": 0}])
        pred_chords = [
            {"root": "C", "start": 0},
            {"root": "C", "start": 0},
        ]
        m = compute_analysis_metrics(None, None, None, None, pred_chords, ref)
        assert m.chord_precision is not None
        assert m.chord_precision <= 1.0
        assert m.chord_recall <= 1.0

    def test_section_one_to_one_no_overcount(self):
        """One predicted section should not match multiple references."""
        ref = Reference(sections=[{"start": 0, "end": 2, "label": "A"}])
        pred_sections = [
            {"start": 0, "end": 2, "label": "A"},
            {"start": 0, "end": 2, "label": "A"},
        ]
        m = compute_analysis_metrics(None, None, None, pred_sections, None, ref)
        assert m.section_precision is not None
        assert m.section_precision <= 1.0


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

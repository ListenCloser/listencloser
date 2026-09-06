"""Tests for real-world corpus infrastructure (no network access)."""

from __future__ import annotations

import io
import json
import os

import numpy as np
import pytest

from evaluation.datasets import cache
from evaluation.datasets.registry import (
    ManualAcquisitionError,
    UnsupportedDatasetError,
    available_datasets,
    get_adapter,
)
from evaluation.models import EvalClip
from evaluation.slicing import (
    slice_beat_annotations,
    slice_chord_annotations,
    slice_midi,
    slice_note_dicts,
    slice_samples,
)

# ── Slicing ──────────────────────────────────────────────────────────────────


class TestAudioSlicing:
    def test_slice_duration(self):
        sr = 1000
        samples = np.arange(2000, dtype=np.float32)  # 2 seconds at 1kHz
        sliced = slice_samples(samples, sr, 0.5, 1.5)
        assert len(sliced) == 1000  # exactly 1 second

    def test_slice_rebase_means_start_index(self):
        sr = 1000
        samples = np.arange(2000, dtype=np.float32)
        sliced = slice_samples(samples, sr, 1.0, 2.0)
        # Rebasing is implicit: slicing [1s, 2s) yields the samples starting at
        # index 1000 (sample value 1000.0), so the first value is 1000.0.
        assert sliced[0] == pytest.approx(1000.0)

    def test_slice_clamps_to_bounds(self):
        sr = 1000
        samples = np.arange(2000, dtype=np.float32)
        sliced = slice_samples(samples, sr, -1.0, 99.0)
        assert len(sliced) == 2000


class TestMidiSlicing:
    def _midi(self, notes) -> bytes:
        import pretty_midi

        pm = pretty_midi.PrettyMIDI(initial_tempo=120)
        inst = pretty_midi.Instrument(program=0)
        for pitch, start, end in notes:
            inst.notes.append(pretty_midi.Note(velocity=80, pitch=pitch, start=start, end=end))
        pm.instruments.append(inst)
        buf = io.BytesIO()
        pm.write(buf)
        return buf.getvalue()

    def test_rebase_and_clip(self):
        midi = self._midi([(60, 5.0, 6.0), (64, 10.0, 10.5), (67, 20.0, 20.5)])
        _out, notes = slice_midi(midi, 5.0, 15.0)
        # First note starts at 5 → rebased to 0; second at 10 → 5; third (20) excluded.
        assert len(notes) == 2
        assert notes[0]["start"] == pytest.approx(0.0, abs=1e-6)
        assert notes[1]["start"] == pytest.approx(5.0, abs=1e-6)

    def test_clip_crossing_boundary(self):
        midi = self._midi([(60, 0.0, 10.0)])
        _out, notes = slice_midi(midi, 2.0, 6.0)
        assert len(notes) == 1
        assert notes[0]["start"] == pytest.approx(0.0, abs=1e-6)
        assert notes[0]["end"] == pytest.approx(4.0, abs=1e-6)

    def test_no_negative_durations(self):
        midi = self._midi([(60, 0.0, 0.05)])
        _out, notes = slice_midi(midi, 0.0, 10.0)
        for n in notes:
            assert n["end"] > n["start"]


class TestBeatSlicing:
    def test_rebase_and_filter(self):
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
        downbeats = [0.0, 2.0]
        # [start, end) half-open: 1.0 and 1.5 are in; 2.0 is excluded.
        s_beats, s_dbs = slice_beat_annotations(beats, downbeats, 1.0, 2.0)
        assert s_beats == [0.0, 0.5]
        assert s_dbs == []

    def test_empty_when_out_of_window(self):
        beats = [0.0, 0.5]
        s_beats, s_dbs = slice_beat_annotations(beats, [], 5.0, 6.0)
        assert s_beats == []
        assert s_dbs == []


class TestChordSlicing:
    def test_rebase_and_filter(self):
        chords = [
            {"root": "C", "start": 0.0, "end": 1.0},
            {"root": "G", "start": 1.0, "end": 2.0},
            {"root": "A", "start": 2.0, "end": 3.0},
        ]
        # [1, 2) window: only the G chord overlaps; rebased to [0, 1].
        result = slice_chord_annotations(chords, 1.0, 2.0)
        assert len(result) == 1
        assert result[0]["start"] == pytest.approx(0.0, abs=1e-6)
        assert result[0]["root"] == "G"


class TestNoteDictSlicing:
    def test_clips_crossing_both_boundaries(self):
        # Note starts before the window and ends after it.
        notes = [{"pitch": 60, "start": 5.0, "end": 25.0, "velocity": 80}]
        result = slice_note_dicts(notes, 10.0, 20.0)
        assert len(result) == 1
        assert result[0]["start"] == pytest.approx(0.0, abs=1e-6)
        assert result[0]["end"] == pytest.approx(10.0, abs=1e-6)

    def test_no_negative_start(self):
        notes = [{"pitch": 60, "start": 8.0, "end": 12.0, "velocity": 80}]
        result = slice_note_dicts(notes, 10.0, 20.0)
        assert result[0]["start"] == pytest.approx(0.0, abs=1e-6)
        assert result[0]["end"] == pytest.approx(2.0, abs=1e-6)

    def test_drops_fully_outside_notes(self):
        notes = [
            {"pitch": 60, "start": 0.0, "end": 1.0, "velocity": 80},
            {"pitch": 64, "start": 30.0, "end": 31.0, "velocity": 80},
        ]
        assert slice_note_dicts(notes, 10.0, 20.0) == []

    def test_end_never_exceeds_excerpt_duration(self):
        notes = [{"pitch": 60, "start": 15.0, "end": 25.0, "velocity": 80}]
        result = slice_note_dicts(notes, 10.0, 20.0)
        assert result[0]["end"] == pytest.approx(10.0, abs=1e-6)


# ── Manifest / models ────────────────────────────────────────────────────────


class TestManifest:
    def test_real_world_manifest_loads(self):
        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "backend",
            "evaluation",
            "corpora",
            "real_world_v1.json",
        )
        path = os.path.abspath(path)
        with open(path) as fh:
            data = json.load(fh)
        assert data["name"] == "real_world_v1"
        assert len(data["clips"]) >= 15
        for clip in data["clips"]:
            assert clip["dataset"] in data["datasets"]
            assert clip["license"]

    def test_clip_parses_dataset_metadata(self):
        clip = EvalClip.from_dict(
            {
                "id": "x",
                "audio": "a.wav",
                "category": "solo_piano",
                "dataset": "maestro",
                "split": "test",
                "source_id": "abc",
                "license": "CC BY-NC-SA 4.0",
                "metrics": ["note_onset"],
                "excerpt_start": 0.0,
                "excerpt_end": 20.0,
            }
        )
        assert clip.dataset == "maestro"
        assert clip.source_id == "abc"
        assert clip.excerpt_end == 20.0
        assert clip.metrics == ["note_onset"]


# ── Dataset registry / cache ─────────────────────────────────────────────────


class TestRegistry:
    def test_adapters_registered(self):
        names = available_datasets()
        for expected in ("maestro", "asap", "guitarset", "slakh"):
            assert expected in names

    def test_unknown_dataset_raises(self):
        with pytest.raises(UnsupportedDatasetError):
            get_adapter("nope")

    def test_adapter_has_license(self):
        for name in ("maestro", "asap", "guitarset", "slakh"):
            adapter = get_adapter(name)
            assert adapter.license

    def test_cache_dir_respects_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MUSIC_EVAL_CACHE_DIR", str(tmp_path))
        assert str(cache.cache_dir()) == str(tmp_path)

    def test_manual_acquisition_is_clear(self):
        # A clip whose files are absent should raise a ManualAcquisitionError.
        adapter = get_adapter("asap")
        with pytest.raises(ManualAcquisitionError):
            adapter.resolve({"source_id": "NoSuch/999", "dataset": "asap"})


class TestMaestroMetadata:
    def _meta(self):
        # Columnar v3.0.0 schema: seven top-level dicts keyed by index.
        return {
            "split": {"0": "train", "1": "test", "2": "validation"},
            "midi_filename": {
                "0": "2004/MIDI-Unprocessed_A_1.midi",
                "1": "2004/MIDI-Unprocessed_04_R1_2004_01-05_ORIG_MID--AUDIO_04_R1_2004_01_Track01_wav.midi",
                "2": "2015/MIDI-Unprocessed_B_1.midi",
            },
            "audio_filename": {
                "0": "2004/MIDI-Unprocessed_A_1.wav",
                "1": "2004/MIDI-Unprocessed_04_R1_2004_01-05_ORIG_MID--AUDIO_04_R1_2004_01_Track01_wav.wav",
                "2": "2015/MIDI-Unprocessed_B_1.wav",
            },
        }

    def test_finds_test_entry_by_source_id(self):
        from evaluation.datasets.maestro import find_test_entry

        full = (
            "2004/MIDI-Unprocessed_04_R1_2004_01-05_ORIG_MID--AUDIO_04_R1_2004_01_Track01_wav.midi"
        )
        entry = find_test_entry(self._meta(), full)
        assert entry is not None
        assert entry["midi_filename"] == full
        assert entry["audio_filename"].endswith(".wav")

    def test_finds_by_unique_suffix(self):
        from evaluation.datasets.maestro import find_test_entry

        entry = find_test_entry(
            self._meta(),
            "MIDI-Unprocessed_04_R1_2004_01-05_ORIG_MID--AUDIO_04_R1_2004_01_Track01_wav.midi",
        )
        assert entry is not None

    def test_does_not_match_train_or_validation(self):
        from evaluation.datasets.maestro import find_test_entry

        assert find_test_entry(self._meta(), "MIDI-Unprocessed_A_1") is None
        assert find_test_entry(self._meta(), "MIDI-Unprocessed_B_1") is None

    def test_missing_source_id_returns_none(self):
        from evaluation.datasets.maestro import find_test_entry

        assert find_test_entry(self._meta(), "Nonexistent_Track") is None

    def test_non_dict_metadata_returns_none(self):
        from evaluation.datasets.maestro import find_test_entry

        assert find_test_entry([], "x") is None
        assert find_test_entry(None, "x") is None

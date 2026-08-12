"""Tests for AMT engine adapter contract (no heavyweight inference)."""

from __future__ import annotations

from evaluation.amt_engines import ENGINES
from evaluation.transcription_metrics import Note


class TestEngineRegistry:
    def test_basic_pitch_and_byte_piano_registered(self):
        assert set(ENGINES.keys()) == {"basic_pitch", "byte_piano"}

    def test_every_engine_has_fn_label_scope(self):
        for _name, meta in ENGINES.items():
            assert callable(meta["fn"])
            assert isinstance(meta["label"], str)
            assert isinstance(meta["scope"], list)

    def test_scopes(self):
        assert "guitar" in ENGINES["basic_pitch"]["scope"]
        assert "full_mix" in ENGINES["basic_pitch"]["scope"]
        assert "piano_stem" in ENGINES["basic_pitch"]["scope"]
        assert ENGINES["byte_piano"]["scope"] == ["piano_stem"]


class TestNoteNormalization:
    def test_canonical_note_fields(self):
        n = Note(60, 0.5, 1.0, 100)
        assert n.pitch == 60
        assert n.start == 0.5
        assert n.end == 1.0
        assert n.velocity == 100

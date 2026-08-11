"""Tests for Beat This! engine registration."""

from __future__ import annotations


class TestBeatThisRegistry:
    def test_beat_this_is_registered_name(self):
        from engines.beats.librosa_engine import LibrosaBeatEngine
        from engines.registry import get_beat_engine

        engine = get_beat_engine("librosa")
        assert isinstance(engine, LibrosaBeatEngine)

    def test_unknown_beat_engine_raises(self):
        import pytest

        from engines.registry import get_beat_engine

        with pytest.raises(ValueError):
            get_beat_engine("nonexistent")

    def test_beat_this_not_installed_fails_at_runtime(self):
        import pytest

        from engines.beats.beat_this_engine import BeatThisEngine
        from engines.registry import get_beat_engine

        engine = get_beat_engine("beat_this")
        assert isinstance(engine, BeatThisEngine)
        with pytest.raises(RuntimeError):
            engine.analyze(b"test")

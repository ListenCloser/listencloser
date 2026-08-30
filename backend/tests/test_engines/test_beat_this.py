"""Tests for Beat This! production registration and beat evidence semantics."""

from __future__ import annotations

import pytest


class TestBeatThisRegistry:
    def test_beat_this_is_production_default(self, monkeypatch):
        """Unconfigured production resolves to the promoted OSS beat engine."""
        from engines.beats.beat_this_engine import BeatThisEngine
        from engines.registry import get_beat_engine

        monkeypatch.delenv("BEAT_ENGINE", raising=False)
        engine = get_beat_engine()
        assert isinstance(engine, BeatThisEngine)

    def test_librosa_remains_explicit_rollback(self, monkeypatch):
        """Operators can roll back without a code change; there is no silent fallback."""
        from engines.beats.librosa_engine import LibrosaBeatEngine
        from engines.registry import get_beat_engine

        monkeypatch.setenv("BEAT_ENGINE", "librosa")
        engine = get_beat_engine()
        assert isinstance(engine, LibrosaBeatEngine)

    def test_explicit_name_overrides_environment(self, monkeypatch):
        from engines.beats.beat_this_engine import BeatThisEngine
        from engines.registry import get_beat_engine

        monkeypatch.setenv("BEAT_ENGINE", "librosa")
        engine = get_beat_engine("beat_this")
        assert isinstance(engine, BeatThisEngine)

    def test_unknown_beat_engine_raises(self):
        from engines.registry import get_beat_engine

        with pytest.raises(ValueError):
            get_beat_engine("nonexistent")

    def test_beat_this_runtime_failure_is_explicit(self):
        from engines.beats.beat_this_engine import BeatThisEngine
        from engines.registry import get_beat_engine

        engine = get_beat_engine("beat_this")
        assert isinstance(engine, BeatThisEngine)
        with pytest.raises((RuntimeError, ImportError, ValueError, OSError)):
            engine.analyze(b"test")


class TestBpmFromBeats:
    """Degenerate beat output must yield no BPM evidence, never a 120 default."""

    def _bpm(self, beats):
        from engines.beats.beat_this_engine import _bpm_from_beats

        return _bpm_from_beats(beats)

    def test_fewer_than_two_beats_is_none(self):
        assert self._bpm([]) is None
        assert self._bpm([1.0]) is None

    def test_no_positive_intervals_is_none(self):
        # Identical or decreasing beat times produce no usable intervals.
        assert self._bpm([1.0, 1.0]) is None
        assert self._bpm([2.0, 1.0]) is None

    def test_healthy_beat_grid_yields_bpm(self):
        bpm = self._bpm([i * 0.5 for i in range(8)])
        assert bpm == pytest.approx(120.0, abs=1e-6)

    def test_result_allows_none_bpm(self):
        from engines.base import BeatTrackingResult, EngineProvenance

        result = BeatTrackingResult(
            bpm=None,
            beats=[1.0],
            downbeats=None,
            beat_positions=[1],
            provenance=EngineProvenance(engine="beat_this", library_version="test"),
        )
        assert result.to_dict()["bpm"] is None

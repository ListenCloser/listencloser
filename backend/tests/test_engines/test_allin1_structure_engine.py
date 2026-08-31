"""Tests for the canonical All-In-One structure engine adapter."""

from __future__ import annotations

import sys
import types

from engines.structure.allin1_engine import AllInOneEngine


def test_disabled_structure_engine_returns_none(monkeypatch, tmp_path):
    monkeypatch.delenv("ALLIN1_ENABLED", raising=False)

    assert AllInOneEngine().analyze(str(tmp_path / "piece.wav")) is None


def test_allin1_result_is_normalized_to_seconds_based_structure(monkeypatch, tmp_path):
    class RawSegment:
        start = 1.23456
        end = 12.34567
        label = "Chorus"

    class RawResult:
        bpm = 119.987
        beats = [0.0, 0.5, 1.0]
        downbeats = [0.0]
        beat_positions = [1, 2, 3]
        segments = [RawSegment()]

    module = types.SimpleNamespace(analyze=lambda *_args, **_kwargs: RawResult())
    monkeypatch.setenv("ALLIN1_ENABLED", "true")
    monkeypatch.setitem(sys.modules, "allin1", module)

    result = AllInOneEngine().analyze(str(tmp_path / "piece.wav"))

    assert result is not None
    assert result.bpm == 119.99
    assert result.segments[0]["label"] == "chorus"
    assert result.segments[0]["start"] == 1.235
    assert result.evidence()["downbeat_count"] == 1

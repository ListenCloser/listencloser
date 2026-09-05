from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from engines.harmony.chordmini_engine import ChordMiniHarmonyEngine, _normalize_chord_label
from engines.registry import get_harmony_engine


def test_registry_resolves_chordmini_without_loading_torch() -> None:
    engine = get_harmony_engine("chordmini")

    assert isinstance(engine, ChordMiniHarmonyEngine)
    assert engine.provenance.engine == "chordmini"
    assert engine.provenance.parameters["experimental"] is True


def test_chordmini_requires_audio_before_checkpoint() -> None:
    engine = ChordMiniHarmonyEngine(checkpoint_path="/does/not/exist.pth")

    with pytest.raises(RuntimeError, match="requires audio input"):
        engine.analyze(b"midi", audio_bytes=None)


def test_chordmini_requires_explicit_checkpoint(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pth"
    engine = ChordMiniHarmonyEngine(checkpoint_path=str(missing))

    with pytest.raises(RuntimeError, match="checkpoint does not exist"):
        engine.analyze(b"", audio_bytes=b"wav")


def test_chordmini_normalizes_labels_without_inventing_theory() -> None:
    assert _normalize_chord_label("C") == ("C", "maj")
    assert _normalize_chord_label("F#:min7") == ("F#", "min7")
    assert _normalize_chord_label("N") == ("N", "N")
    assert _normalize_chord_label("X") == ("X", "X")


def test_chordmini_adapts_inference_segments_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint = tmp_path / "2e1d_model_best.pth"
    checkpoint.write_bytes(b"test checkpoint")
    audio_bytes = b"RIFF-test-wav"

    def fake_infer(audio_path: str, checkpoint_path: Path) -> SimpleNamespace:
        assert Path(audio_path).read_bytes() == audio_bytes
        assert checkpoint_path == checkpoint
        return SimpleNamespace(
            segments=[
                (0.0, 1.2345, "C:maj7"),
                (1.2345, 2.5, "N"),
                (2.5, 3.0, "G:7"),
            ],
            checkpoint_sha256="abc123",
            frame_duration=2048 / 22050,
            frame_count=32,
        )

    fake_runtime = SimpleNamespace(infer_chords=fake_infer)
    monkeypatch.setitem(sys.modules, "engines.harmony._chordmini_runtime", fake_runtime)

    engine = ChordMiniHarmonyEngine(checkpoint_path=str(checkpoint))
    result = engine.analyze(b"unused midi", audio_bytes=audio_bytes)

    assert result.key is None
    assert result.roman_numerals == []
    assert result.cadences == []
    assert result.voice_leading is None
    assert result.phrases == []
    assert result.chords == [
        {"root": "C", "quality": "maj7", "start": 0.0, "end": 1.234},
        {"root": "N", "quality": "N", "start": 1.234, "end": 2.5},
        {"root": "G", "quality": "7", "start": 2.5, "end": 3.0},
    ]
    assert result.provenance.engine == "chordmini"
    assert result.provenance.model == "2e1d_model_best.pth"
    assert result.provenance.parameters["checkpoint_sha256"] == "abc123"
    assert result.component_provenance["chords"] == result.provenance

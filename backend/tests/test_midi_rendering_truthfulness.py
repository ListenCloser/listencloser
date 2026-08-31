from __future__ import annotations

import sys

import pytest

import music_features


def test_midi_rendering_fails_closed_when_soundfont_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(music_features, "SOUNDFONT_PATH", "/definitely/missing/listencloser.sf2")

    with pytest.raises(RuntimeError, match="SoundFont is unavailable"):
        music_features.midi_to_wav(b"not-read-before-soundfont-check")


def test_midi_rendering_fails_closed_when_fluidsynth_runtime_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(music_features.os.path, "exists", lambda _path: True)
    monkeypatch.setitem(sys.modules, "fluidsynth", None)

    with pytest.raises(RuntimeError, match="FluidSynth Python runtime is unavailable"):
        music_features.midi_to_wav(b"not-read-before-import-check")


def test_repository_owned_numpy_synth_is_not_a_runtime_fallback() -> None:
    assert not hasattr(music_features, "_midi_to_wav_numpy")

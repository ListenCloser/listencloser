from __future__ import annotations

import io
import sys
import types

import pretty_midi

import music_features


def _empty_midi_bytes() -> bytes:
    midi = pretty_midi.PrettyMIDI()
    out = io.BytesIO()
    midi.write(out)
    return out.getvalue()


def _fake_basic_pitch_modules(monkeypatch, *, model_factory=None, predict=None) -> None:
    package = types.ModuleType("basic_pitch")
    package.__path__ = []
    package.ICASSP_2022_MODEL_PATH = "/models/basic-pitch"

    inference = types.ModuleType("basic_pitch.inference")
    if model_factory is not None:
        inference.Model = model_factory
    if predict is not None:
        inference.predict = predict

    monkeypatch.setitem(sys.modules, "basic_pitch", package)
    monkeypatch.setitem(sys.modules, "basic_pitch.inference", inference)


def test_basic_pitch_model_is_loaded_once_per_process(monkeypatch):
    constructed: list[str] = []

    class FakeModel:
        def __init__(self, path: str) -> None:
            constructed.append(path)

    _fake_basic_pitch_modules(monkeypatch, model_factory=FakeModel)
    monkeypatch.setattr(music_features, "_basic_pitch_model", None)

    first = music_features._get_basic_pitch_model()
    second = music_features._get_basic_pitch_model()

    assert first is second
    assert constructed == ["/models/basic-pitch"]


def test_transcribe_passes_cached_model_without_changing_thresholds(monkeypatch):
    midi_bytes = _empty_midi_bytes()
    cached_model = object()
    captured: dict[str, object] = {}

    class FakeMidiData:
        def write(self, path: str) -> None:
            with open(path, "wb") as handle:
                handle.write(midi_bytes)

    def fake_predict(
        audio_path: str,
        *,
        model_or_model_path,
        onset_threshold: float,
        frame_threshold: float,
    ):
        captured.update(
            {
                "audio_path": audio_path,
                "model": model_or_model_path,
                "onset_threshold": onset_threshold,
                "frame_threshold": frame_threshold,
            }
        )
        return {}, FakeMidiData(), []

    _fake_basic_pitch_modules(monkeypatch, predict=fake_predict)
    monkeypatch.setattr(music_features, "_get_basic_pitch_model", lambda: cached_model)
    monkeypatch.setattr(music_features, "midi_to_wav", lambda _midi: b"wav")

    result = music_features.transcribe_audio(
        b"fixture bytes",
        fmt="wav",
        onset_threshold=0.61,
        frame_threshold=0.42,
    )

    assert captured["model"] is cached_model
    assert captured["onset_threshold"] == 0.61
    assert captured["frame_threshold"] == 0.42
    assert result["wav"] == b"wav"
    assert result["num_notes"] == 0

from __future__ import annotations

import sys
import types

import numpy as np

from domain import worker_warmup


def test_basic_pitch_prewarm_uses_short_non_silent_inference(monkeypatch):
    captured: dict[str, object] = {}

    package = types.ModuleType("basic_pitch")
    package.__path__ = []
    inference = types.ModuleType("basic_pitch.inference")

    def fake_predict(path: str):
        import soundfile as sf

        signal, sample_rate = sf.read(path, dtype="float32")
        captured.update({"signal": signal, "sample_rate": sample_rate})
        return {}, object(), [(0.0, 1.0, 69, 0.8, None)]

    inference.predict = fake_predict
    monkeypatch.setitem(sys.modules, "basic_pitch", package)
    monkeypatch.setitem(sys.modules, "basic_pitch.inference", inference)
    monkeypatch.delenv("TRANSCRIPTION_ENGINE", raising=False)

    assert worker_warmup.prewarm_basic_pitch() is True

    signal = captured["signal"]
    assert isinstance(signal, np.ndarray)
    assert signal.dtype == np.float32
    assert signal.shape == (22050,)
    assert np.max(np.abs(signal)) > 0.0
    assert captured["sample_rate"] == 22050


def test_basic_pitch_prewarm_skips_when_default_engine_changes(monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_ENGINE", "transkun")

    assert worker_warmup.prewarm_basic_pitch() is False


def test_librosa_prewarm_uses_non_silent_score_call_shape(monkeypatch):
    import librosa

    captured: dict[str, object] = {}

    def fake_beat_track(*, y, sr, trim):
        captured.update({"y": y, "sr": sr, "trim": trim})
        return np.asarray([120.0]), np.asarray([10, 20], dtype=int)

    monkeypatch.delenv("BEAT_ENGINE", raising=False)
    monkeypatch.setattr(librosa.beat, "beat_track", fake_beat_track)

    assert worker_warmup.prewarm_librosa_beat_tracking() is True

    signal = captured["y"]
    assert isinstance(signal, np.ndarray)
    assert signal.dtype == np.float32
    assert signal.shape == (22050 * 4,)
    click_positions = np.flatnonzero(signal)
    assert click_positions.size >= 4
    assert click_positions[0] > 0
    assert np.all(signal[click_positions] == 1.0)
    assert captured["sr"] == 22050
    assert captured["trim"] is False


def test_librosa_prewarm_click_train_has_nonempty_onset_envelope():
    import librosa

    signal = worker_warmup._librosa_prewarm_signal()
    onset_envelope = librosa.onset.onset_strength(
        y=signal,
        sr=22050,
        aggregate=np.median,
    )

    # Upstream beat_track returns before tempo/DP work when this is all zeros.
    assert onset_envelope.any()


def test_librosa_prewarm_skips_when_default_engine_changes(monkeypatch):
    monkeypatch.setenv("BEAT_ENGINE", "beat_this")

    assert worker_warmup.prewarm_librosa_beat_tracking() is False

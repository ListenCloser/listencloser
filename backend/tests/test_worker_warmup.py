from __future__ import annotations

import wave

import numpy as np
import pytest

from domain import worker_warmup


@pytest.mark.integration
def test_basic_pitch_prewarm_uses_normal_predict_call_shape(monkeypatch):
    import basic_pitch.inference as inference

    captured: dict[str, object] = {}

    def fake_predict(audio_path, *, onset_threshold, frame_threshold):
        with wave.open(str(audio_path), "rb") as wav_file:
            captured.update(
                {
                    "channels": wav_file.getnchannels(),
                    "sample_width": wav_file.getsampwidth(),
                    "sample_rate": wav_file.getframerate(),
                    "frames": wav_file.readframes(wav_file.getnframes()),
                    "onset_threshold": onset_threshold,
                    "frame_threshold": frame_threshold,
                }
            )
        return {}, object(), []

    monkeypatch.delenv("TRANSCRIPTION_ENGINE", raising=False)
    monkeypatch.setattr(inference, "predict", fake_predict)

    assert worker_warmup.prewarm_basic_pitch_inference() is True

    pcm = np.frombuffer(captured["frames"], dtype="<i2")
    assert pcm.size == int(22050 * 0.5)
    assert np.any(pcm != 0)
    assert captured["channels"] == 1
    assert captured["sample_width"] == 2
    assert captured["sample_rate"] == 22050
    assert captured["onset_threshold"] == 0.5
    assert captured["frame_threshold"] == 0.3


def test_basic_pitch_prewarm_skips_when_default_engine_changes(monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_ENGINE", "transkun")

    assert worker_warmup.prewarm_basic_pitch_inference() is False


def test_beat_this_prewarm_is_default(monkeypatch):
    import engines.beats.beat_this_engine as beat_this_engine

    calls = []
    monkeypatch.delenv("BEAT_ENGINE", raising=False)
    monkeypatch.setattr(beat_this_engine, "prewarm_beat_this_model", lambda: calls.append("loaded"))

    assert worker_warmup.prewarm_beat_this_inference() is True
    assert calls == ["loaded"]


def test_beat_this_prewarm_skips_for_librosa_rollback(monkeypatch):
    monkeypatch.setenv("BEAT_ENGINE", "librosa")

    assert worker_warmup.prewarm_beat_this_inference() is False


def test_librosa_prewarm_uses_non_silent_score_call_shape_when_selected(monkeypatch):
    import librosa

    captured: dict[str, object] = {}

    def fake_beat_track(*, y, sr, trim):
        captured.update({"y": y, "sr": sr, "trim": trim})
        return np.asarray([120.0]), np.asarray([10, 20], dtype=int)

    monkeypatch.setenv("BEAT_ENGINE", "librosa")
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


def test_librosa_prewarm_skips_under_production_default(monkeypatch):
    monkeypatch.delenv("BEAT_ENGINE", raising=False)

    assert worker_warmup.prewarm_librosa_beat_tracking() is False

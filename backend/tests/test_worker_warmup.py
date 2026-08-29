from __future__ import annotations

import numpy as np

from domain import worker_warmup


def test_librosa_prewarm_uses_score_call_shape(monkeypatch):
    import librosa

    captured: dict[str, object] = {}

    def fake_beat_track(*, y, sr, trim):
        captured.update({"y": y, "sr": sr, "trim": trim})
        return 0.0, np.asarray([], dtype=int)

    monkeypatch.delenv("BEAT_ENGINE", raising=False)
    monkeypatch.setattr(librosa.beat, "beat_track", fake_beat_track)

    assert worker_warmup.prewarm_librosa_beat_tracking() is True

    signal = captured["y"]
    assert isinstance(signal, np.ndarray)
    assert signal.dtype == np.float32
    assert signal.shape == (22050,)
    assert np.count_nonzero(signal) == 0
    assert captured["sr"] == 22050
    assert captured["trim"] is False


def test_librosa_prewarm_skips_when_default_engine_changes(monkeypatch):
    monkeypatch.setenv("BEAT_ENGINE", "beat_this")

    assert worker_warmup.prewarm_librosa_beat_tracking() is False

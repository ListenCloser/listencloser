from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from backend.evaluation.analysis_v3.separation import run_musdb_real


def test_channel_first_accepts_mono_and_both_stereo_layouts():
    mono = np.arange(8, dtype=np.float32)
    channel_first = np.stack([mono, mono + 1])
    channel_last = channel_first.T

    assert run_musdb_real._channel_first(mono).shape == (1, 8)
    assert np.array_equal(run_musdb_real._channel_first(channel_first), channel_first)
    assert np.array_equal(run_musdb_real._channel_first(channel_last), channel_first)


def test_si_sdr_uses_standardized_wrapper_and_averages_channels(monkeypatch):
    calls = []

    def fake_si_sdr(reference, estimate, **kwargs):
        calls.append((reference.copy(), estimate.copy(), kwargs))
        return np.array([3.0 + len(calls)], dtype=np.float32)

    monkeypatch.setitem(sys.modules, "fast_bss_eval", SimpleNamespace(si_sdr=fake_si_sdr))
    reference = np.ones((2, 16), dtype=np.float32)
    estimate = np.full((2, 16), 0.5, dtype=np.float32)

    score = run_musdb_real._si_sdr_mean(reference, estimate)

    assert score == pytest.approx(4.5)
    assert len(calls) == 2
    assert all(call[2] == {"zero_mean": True, "clamp_db": 100.0} for call in calls)


def test_si_sdr_withholds_silent_reference(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "fast_bss_eval",
        SimpleNamespace(si_sdr=lambda *args, **kwargs: np.array([1.0])),
    )
    reference = np.zeros((2, 8), dtype=np.float32)
    estimate = np.ones((2, 8), dtype=np.float32)

    assert run_musdb_real._si_sdr_mean(reference, estimate) is None


def test_summarize_keeps_per_stem_distribution_and_counts():
    rows = [
        {"stem": "drums", "status": "scored", "delta_si_sdr_db": 2.0},
        {"stem": "drums", "status": "scored", "delta_si_sdr_db": -1.0},
        {"stem": "bass", "status": "scored", "delta_si_sdr_db": 3.0},
        {"stem": "other", "status": "withheld_silent_reference"},
    ]

    summary = run_musdb_real._summarize(rows)

    assert summary["drums"]["scored"] == 2
    assert summary["drums"]["mean_delta_si_sdr_db"] == pytest.approx(0.5)
    assert summary["drums"]["improved"] == 1
    assert summary["drums"]["degraded"] == 1
    assert summary["bass"]["mean_delta_si_sdr_db"] == pytest.approx(3.0)
    assert summary["other"] == {"scored": 0}
    assert summary["vocals"] == {"scored": 0}


def test_non_cpu_device_is_rejected_before_heavy_imports():
    with pytest.raises(ValueError, match="intentionally CPU-only"):
        run_musdb_real.run(device="cuda", max_tracks=1)

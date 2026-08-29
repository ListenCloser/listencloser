from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from backend.evaluation.analysis_v3.separation import run_operational_v2


def test_synthetic_audio_is_deterministic_and_exact_duration():
    first = run_operational_v2._synthetic_audio(0.25, sample_rate=8000)
    second = run_operational_v2._synthetic_audio(0.25, sample_rate=8000)

    assert first.dtype == np.float32
    assert first.shape == (2000,)
    assert np.array_equal(first, second)


def test_synthetic_audio_rejects_nonpositive_duration():
    with pytest.raises(ValueError, match="duration_seconds must be positive"):
        run_operational_v2._synthetic_audio(0.0)


def test_max_rss_converts_linux_kib_to_mb(monkeypatch):
    monkeypatch.setattr(run_operational_v2.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        run_operational_v2.resource,
        "getrusage",
        lambda who: SimpleNamespace(ru_maxrss=2048.0),
    )

    assert run_operational_v2._max_rss_mb() == pytest.approx(2.0)


def test_max_rss_converts_macos_bytes_to_mb(monkeypatch):
    monkeypatch.setattr(run_operational_v2.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        run_operational_v2.resource,
        "getrusage",
        lambda who: SimpleNamespace(ru_maxrss=2.0 * 1024.0 * 1024.0),
    )

    assert run_operational_v2._max_rss_mb() == pytest.approx(2.0)


def test_operational_probe_rejects_non_cpu_device():
    with pytest.raises(ValueError, match="intentionally CPU-only"):
        run_operational_v2.run_operational_probe(device="cuda")

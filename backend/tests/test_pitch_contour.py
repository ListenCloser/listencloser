import sys
from types import SimpleNamespace

import numpy as np
import pytest

from domain.models import Capability, Job
from domain.pitch_contour_capability import _requested_engine
from engines.pitch.pyin import frames_from_estimates, hz_to_midi_cents
from engines.pitch.registry import estimate_pitch_contour


def test_hz_to_midi_cents_uses_a440_absolute_reference():
    assert hz_to_midi_cents(440.0) == pytest.approx(6900.0)
    assert hz_to_midi_cents(220.0) == pytest.approx(5700.0)


def test_frames_preserve_coordinates_voicing_probability_and_unvoiced_nulls():
    frames = frames_from_estimates(
        np.array([440.0, np.nan, 445.0]),
        np.array([True, False, True]),
        np.array([0.98, 0.04, 0.91]),
        sample_rate_hz=22050,
        hop_length_samples=220,
    )

    assert frames[0] == {
        "frame": 0,
        "time_seconds": 0.0,
        "pitch_hz": 440.0,
        "pitch_cents": pytest.approx(6900.0),
        "voiced": True,
        "voiced_probability": 0.98,
    }
    assert frames[1]["time_seconds"] == pytest.approx(220 / 22050)
    assert frames[1]["pitch_hz"] is None
    assert frames[1]["pitch_cents"] is None
    assert frames[1]["voiced"] is False
    assert frames[1]["voiced_probability"] == pytest.approx(0.04)
    assert frames[2]["frame"] == 2
    assert frames[2]["pitch_hz"] == pytest.approx(445.0)


def test_pitch_job_defaults_to_pyin_and_accepts_explicit_alternates():
    capability = Capability(name="pitch_contour", version="1.0")

    assert (
        _requested_engine(
            Job(workflow_id="00000000-0000-0000-0000-000000000001", capability=capability)
        )
        == "pyin"
    )
    assert (
        _requested_engine(
            Job(
                workflow_id="00000000-0000-0000-0000-000000000001",
                capability=capability,
                parameters={"pitch_engine": "torchcrepe"},
            )
        )
        == "torchcrepe"
    )
    assert (
        _requested_engine(
            Job(
                workflow_id="00000000-0000-0000-0000-000000000001",
                capability=capability,
                parameters={"pitch_engine": "pesto"},
            )
        )
        == "pesto"
    )


def test_pitch_job_rejects_unknown_engine():
    job = Job(
        workflow_id="00000000-0000-0000-0000-000000000001",
        capability=Capability(name="pitch_contour", version="1.0"),
        parameters={"pitch_engine": "mystery"},
    )

    with pytest.raises(ValueError, match="unsupported pitch contour engine"):
        _requested_engine(job)


def test_pitch_registry_routes_alternates_without_silent_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    torchcrepe_result = {"engine": {"name": "torchcrepe"}, "frames": []}
    pesto_result = {"engine": {"name": "pesto"}, "frames": []}
    monkeypatch.setitem(
        sys.modules,
        "engines.pitch.torchcrepe_engine",
        SimpleNamespace(estimate_pitch_contour=lambda _: torchcrepe_result),
    )
    monkeypatch.setitem(
        sys.modules,
        "engines.pitch.pesto_engine",
        SimpleNamespace(estimate_pitch_contour=lambda _: pesto_result),
    )

    assert estimate_pitch_contour(b"wav", "torchcrepe") is torchcrepe_result
    assert estimate_pitch_contour(b"wav", "pesto") is pesto_result
    with pytest.raises(ValueError, match="Unknown pitch contour engine"):
        estimate_pitch_contour(b"wav", "mystery")

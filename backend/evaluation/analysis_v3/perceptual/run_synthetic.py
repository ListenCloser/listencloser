"""Run deterministic synthetic validation for the first #455 perceptual evidence slice."""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from .features import (
    onset_strength_series,
    relative_band_energy_series,
    rms_series,
    spectral_centroid_series,
)

SAMPLE_RATE = 22_050


def _sine(frequency_hz: float, duration_seconds: float, amplitude: float = 1.0) -> np.ndarray:
    times = np.arange(int(SAMPLE_RATE * duration_seconds), dtype=float) / SAMPLE_RATE
    return amplitude * np.sin(2.0 * np.pi * frequency_hz * times)


def _window_values(series: Any, start_seconds: float, end_seconds: float) -> np.ndarray:
    times = np.asarray(series.frame_times_seconds)
    values = np.asarray(series.values)
    mask = np.logical_and(times >= start_seconds, times <= end_seconds)
    if not np.any(mask):
        raise ValueError("probe window contains no feature frames")
    return values[mask]


def run_synthetic_validation() -> dict[str, Any]:
    probes: list[dict[str, Any]] = []

    amplitude_audio = np.concatenate([_sine(440.0, 1.0, 0.1), _sine(440.0, 1.0, 0.8)])
    amplitude_series = rms_series(amplitude_audio, SAMPLE_RATE)
    quiet_rms = float(np.median(_window_values(amplitude_series, 0.2, 0.8)))
    loud_rms = float(np.median(_window_values(amplitude_series, 1.2, 1.8)))
    rms_ratio = loud_rms / quiet_rms
    probes.append(
        {
            "id": "amplitude_step_rms",
            "measured": {"quiet_rms": quiet_rms, "loud_rms": loud_rms, "ratio": rms_ratio},
            "expectation": "7.5 <= ratio <= 8.5",
            "passed": 7.5 <= rms_ratio <= 8.5,
        }
    )

    spectral_audio = np.concatenate([_sine(220.0, 1.0), _sine(4_000.0, 1.0)])
    spectral_series = spectral_centroid_series(spectral_audio, SAMPLE_RATE)
    low_centroid = float(np.median(_window_values(spectral_series, 0.2, 0.8)))
    high_centroid = float(np.median(_window_values(spectral_series, 1.2, 1.8)))
    probes.append(
        {
            "id": "frequency_shift_centroid",
            "measured": {"low_hz": low_centroid, "high_hz": high_centroid},
            "expectation": "low within 15 Hz of 220 and high within 30 Hz of 4000",
            "passed": abs(low_centroid - 220.0) <= 15.0 and abs(high_centroid - 4_000.0) <= 30.0,
        }
    )

    low_band = relative_band_energy_series(_sine(100.0, 2.0), SAMPLE_RATE)
    high_band = relative_band_energy_series(_sine(6_000.0, 2.0), SAMPLE_RATE)
    low_values = np.median(_window_values(low_band, 0.2, 1.8), axis=0)
    high_values = np.median(_window_values(high_band, 0.2, 1.8), axis=0)
    probes.append(
        {
            "id": "coarse_band_separation",
            "measured": {
                "100hz_low_fraction": float(low_values[0]),
                "100hz_high_fraction": float(low_values[3]),
                "6000hz_low_fraction": float(high_values[0]),
                "6000hz_high_fraction": float(high_values[3]),
            },
            "expectation": "target band fraction > 0.98 and opposite extreme < 0.01",
            "passed": bool(
                low_values[0] > 0.98
                and low_values[3] < 0.01
                and high_values[3] > 0.98
                and high_values[0] < 0.01
            ),
        }
    )

    gain_reference = relative_band_energy_series(_sine(100.0, 2.0), SAMPLE_RATE)
    gain_scaled = relative_band_energy_series(_sine(100.0, 2.0, 0.2), SAMPLE_RATE)
    reference_values = _window_values(gain_reference, 0.2, 1.8)
    scaled_values = _window_values(gain_scaled, 0.2, 1.8)
    max_gain_delta = float(np.max(np.abs(reference_values - scaled_values)))
    probes.append(
        {
            "id": "relative_band_gain_invariance",
            "measured": {"max_absolute_delta": max_gain_delta},
            "expectation": "max absolute band-ratio delta <= 1e-5",
            "passed": max_gain_delta <= 1e-5,
        }
    )

    clicks = np.zeros(SAMPLE_RATE * 4, dtype=np.float32)
    for seconds in np.arange(0.25, 2.0, 0.5):
        clicks[int(seconds * SAMPLE_RATE)] = 1.0
    for seconds in np.arange(2.05, 4.0, 0.125):
        clicks[int(seconds * SAMPLE_RATE)] = 1.0
    onset_series = onset_strength_series(clicks, SAMPLE_RATE)
    sparse_onset = float(np.mean(_window_values(onset_series, 0.2, 1.9)))
    dense_onset = float(np.mean(_window_values(onset_series, 2.1, 3.9)))
    onset_ratio = dense_onset / sparse_onset
    probes.append(
        {
            "id": "transient_density_onset_strength",
            "measured": {
                "sparse_mean": sparse_onset,
                "dense_mean": dense_onset,
                "ratio": onset_ratio,
            },
            "expectation": "dense onset-strength mean > 2x sparse mean",
            "passed": onset_ratio > 2.0,
        }
    )

    return {
        "evidence_class": "DETERMINISTIC_SYNTHETIC_VALIDATION",
        "scope": "evaluation_only",
        "sample_rate": SAMPLE_RATE,
        "versions": {"librosa": version("librosa"), "numpy": version("numpy")},
        "all_passed": all(bool(probe["passed"]) for probe in probes),
        "probes": probes,
        "semantic_claims": "none; measured descriptors only",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = run_synthetic_validation()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")

    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

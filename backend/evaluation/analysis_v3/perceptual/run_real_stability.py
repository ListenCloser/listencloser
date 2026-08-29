"""Measure real-audio stability of the small #455 perceptual evidence set.

This runner reports literal descriptor sensitivity. It intentionally does not
convert measurements into perceptual adjectives or declare universal musical
thresholds.
"""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

import librosa
import numpy as np

from .features import FeatureSeries, extract_baseline_perceptual_evidence


def _load_mono(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = librosa.load(path, sr=None, mono=True)
    samples = np.asarray(audio, dtype=np.float32)
    if samples.size == 0:
        raise ValueError(f"decoded audio is empty: {path}")
    if not np.isfinite(samples).all():
        raise ValueError(f"decoded audio contains non-finite samples: {path}")
    return samples, int(sample_rate)


def _feature_values(series: FeatureSeries) -> np.ndarray:
    values = np.asarray(series.values, dtype=float)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError(f"feature {series.feature!r} is empty or non-finite")
    return values


def _aggregate(values: np.ndarray) -> np.ndarray:
    return np.asarray(np.median(values, axis=0), dtype=float)


def _json_number(value: np.ndarray) -> float | list[float]:
    if value.ndim == 0:
        return float(value)
    return value.astype(float).tolist()


def summarize_evidence(evidence: dict[str, FeatureSeries]) -> dict[str, dict[str, Any]]:
    """Return deterministic aggregate/range summaries in each feature's native units."""
    summaries: dict[str, dict[str, Any]] = {}
    for name, series in evidence.items():
        values = _feature_values(series)
        summaries[name] = {
            "unit": series.unit,
            "normalization": series.normalization,
            "median": _json_number(_aggregate(values)),
            "p10": _json_number(np.asarray(np.percentile(values, 10, axis=0), dtype=float)),
            "p90": _json_number(np.asarray(np.percentile(values, 90, axis=0), dtype=float)),
            "frames": int(values.shape[0]),
        }
    return summaries


def _aggregate_delta(
    reference: dict[str, FeatureSeries],
    perturbed: dict[str, FeatureSeries],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in sorted(reference):
        reference_aggregate = _aggregate(_feature_values(reference[name]))
        perturbed_aggregate = _aggregate(_feature_values(perturbed[name]))
        delta = perturbed_aggregate - reference_aggregate
        denominator = np.maximum(np.abs(reference_aggregate), 1e-12)
        relative = delta / denominator
        result[name] = {
            "reference_median": _json_number(reference_aggregate),
            "perturbed_median": _json_number(perturbed_aggregate),
            "delta": _json_number(delta),
            "relative_delta": _json_number(relative),
        }
    return result


def _span_aggregate(
    series: FeatureSeries,
    start_seconds: float,
    end_seconds: float,
) -> np.ndarray:
    times = np.asarray(series.frame_times_seconds, dtype=float)
    values = _feature_values(series)
    mask = np.logical_and(times >= start_seconds, times < end_seconds)
    if not np.any(mask):
        raise ValueError(f"span {start_seconds:.3f}-{end_seconds:.3f} contains no frames")
    return _aggregate(values[mask])


def _boundary_sensitivity(
    evidence: dict[str, FeatureSeries],
    duration_seconds: float,
    *,
    span_seconds: float = 10.0,
    shift_seconds: float = 0.5,
) -> dict[str, Any] | None:
    if duration_seconds < span_seconds + shift_seconds + 1.0:
        return None

    max_start = duration_seconds - span_seconds - shift_seconds
    start = min(max(1.0, duration_seconds * 0.25), max_start)
    end = start + span_seconds
    shifted_start = start + shift_seconds
    shifted_end = end + shift_seconds

    features: dict[str, dict[str, Any]] = {}
    for name, series in evidence.items():
        reference = _span_aggregate(series, start, end)
        shifted = _span_aggregate(series, shifted_start, shifted_end)
        delta = shifted - reference
        denominator = np.maximum(np.abs(reference), 1e-12)
        features[name] = {
            "reference_median": _json_number(reference),
            "shifted_median": _json_number(shifted),
            "delta": _json_number(delta),
            "relative_delta": _json_number(delta / denominator),
        }

    return {
        "reference_span_seconds": [start, end],
        "shifted_span_seconds": [shifted_start, shifted_end],
        "shift_seconds": shift_seconds,
        "features": features,
    }


def probe_track(path: Path, *, codec_variant: Path | None = None) -> dict[str, Any]:
    """Run raw stability measurements for one real recording."""
    audio, sample_rate = _load_mono(path)
    duration_seconds = float(len(audio) / sample_rate)
    baseline = extract_baseline_perceptual_evidence(audio, sample_rate)

    gain_scaled = extract_baseline_perceptual_evidence(audio * 0.5, sample_rate)

    target_sample_rate = 16_000 if sample_rate != 16_000 else 22_050
    resampled_audio = librosa.resample(
        audio,
        orig_sr=sample_rate,
        target_sr=target_sample_rate,
    ).astype(np.float32)
    resampled = extract_baseline_perceptual_evidence(resampled_audio, target_sample_rate)

    result: dict[str, Any] = {
        "path": str(path),
        "sample_rate": sample_rate,
        "duration_seconds": duration_seconds,
        "baseline": summarize_evidence(baseline),
        "gain_x0_5": _aggregate_delta(baseline, gain_scaled),
        "resampled": {
            "target_sample_rate": target_sample_rate,
            "aggregate_delta": _aggregate_delta(baseline, resampled),
        },
        "boundary_shift": _boundary_sensitivity(baseline, duration_seconds),
    }

    if codec_variant is not None:
        codec_audio, codec_sample_rate = _load_mono(codec_variant)
        codec_evidence = extract_baseline_perceptual_evidence(codec_audio, codec_sample_rate)
        result["codec_variant"] = {
            "path": str(codec_variant),
            "sample_rate": codec_sample_rate,
            "aggregate_delta": _aggregate_delta(baseline, codec_evidence),
        }

    return result


def run_probe(
    tracks: list[tuple[str, Path, Path | None]],
) -> dict[str, Any]:
    """Run a provenance-labeled collection of real-audio probes."""
    return {
        "evidence_class": "REAL_AUDIO_DESCRIPTOR_STABILITY",
        "scope": "evaluation_only",
        "semantic_claims": "none; literal descriptor sensitivity only",
        "versions": {
            "librosa": version("librosa"),
            "numpy": version("numpy"),
        },
        "tracks": [
            {
                "id": track_id,
                **probe_track(path, codec_variant=codec_variant),
            }
            for track_id, path, codec_variant in tracks
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--track",
        action="append",
        nargs=2,
        metavar=("ID", "PATH"),
        default=[],
        help="Track id and original audio path; repeat for multiple tracks",
    )
    parser.add_argument(
        "--codec-variant",
        action="append",
        nargs=2,
        metavar=("ID", "PATH"),
        default=[],
        help="Optional codec variant keyed by the same track id",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    codec_paths = {track_id: Path(path) for track_id, path in args.codec_variant}
    tracks = [
        (track_id, Path(path), codec_paths.get(track_id)) for track_id, path in args.track
    ]
    if not tracks:
        parser.error("at least one --track is required")

    result = run_probe(tracks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

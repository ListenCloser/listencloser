"""Measure Beat This model lifecycle cost on production-shaped audio.

This benchmark isolates the current production wrapper's main lifecycle question:
whether constructing a fresh ``File2Beats`` for every Analysis call is materially
more expensive than retaining an already-used model in the worker process.

It intentionally does not change production behavior. The result is suitable for
CI artifact retention and for deciding whether a later production model-lifecycle
change is justified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import tempfile
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

import music_features


def _timed(callable_obj):
    started = time.perf_counter()
    value = callable_obj()
    return time.perf_counter() - started, value


def _normalise_times(values: Any) -> list[float]:
    array = np.asarray(values, dtype=float).reshape(-1)
    return [float(value) for value in array]


def _output_signature(beats: Any, downbeats: Any) -> dict[str, Any]:
    payload = {
        "beats": [round(value, 6) for value in _normalise_times(beats)],
        "downbeats": [round(value, 6) for value in _normalise_times(downbeats)],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {
        "beat_count": len(payload["beats"]),
        "downbeat_count": len(payload["downbeats"]),
        "sha256_rounded_1e_6": hashlib.sha256(encoded).hexdigest(),
    }


def _equivalent(reference: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return reference == candidate


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "median_seconds": round(statistics.median(values), 6),
        "min_seconds": round(min(values), 6),
        "max_seconds": round(max(values), 6),
    }


def benchmark(input_path: Path, fmt: str, trials: int = 3) -> dict[str, Any]:
    """Run cold, retained-model, and reconstruct-per-call Beat This timings."""
    if trials < 2:
        raise ValueError("trials must be >= 2")

    raw_audio = input_path.read_bytes()
    wav_bytes = music_features.decode_audio_to_wav(raw_audio, fmt=fmt)

    # Import after decode so audio-format preparation is outside the model timing.
    from beat_this.inference import File2Beats  # type: ignore[import-untyped]

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            handle.write(wav_bytes)
            handle.flush()
            tmp_path = handle.name

        cold_construct_s, retained_model = _timed(lambda: File2Beats(device="cpu"))
        cold_inference_s, cold_output = _timed(lambda: retained_model(tmp_path))
        reference = _output_signature(*cold_output)

        retained_inference_seconds: list[float] = []
        retained_equivalent: list[bool] = []
        for _ in range(trials):
            duration_s, output = _timed(lambda: retained_model(tmp_path))
            retained_inference_seconds.append(duration_s)
            retained_equivalent.append(_equivalent(reference, _output_signature(*output)))

        reconstructed_construct_seconds: list[float] = []
        reconstructed_inference_seconds: list[float] = []
        reconstructed_total_seconds: list[float] = []
        reconstructed_equivalent: list[bool] = []
        for _ in range(trials):
            construct_s, model = _timed(lambda: File2Beats(device="cpu"))
            inference_s, output = _timed(lambda: model(tmp_path))
            reconstructed_construct_seconds.append(construct_s)
            reconstructed_inference_seconds.append(inference_s)
            reconstructed_total_seconds.append(construct_s + inference_s)
            reconstructed_equivalent.append(_equivalent(reference, _output_signature(*output)))

        all_equivalent = all(retained_equivalent) and all(reconstructed_equivalent)
        retained_median = statistics.median(retained_inference_seconds)
        reconstructed_median = statistics.median(reconstructed_total_seconds)
        savings_s = reconstructed_median - retained_median
        speedup = reconstructed_median / retained_median if retained_median > 0 else None

        return {
            "schema_version": 1,
            "scenario": "beat_this_model_lifecycle",
            "thresholds_enforced": False,
            "release_sha": os.environ.get("GITHUB_SHA"),
            "fixture": input_path.name,
            "fixture_sha256": hashlib.sha256(raw_audio).hexdigest(),
            "decoded_wav_sha256": hashlib.sha256(wav_bytes).hexdigest(),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "beat_this": version("beat-this"),
                "device": "cpu",
            },
            "reference_output": reference,
            "outputs_equivalent": all_equivalent,
            "cold": {
                "construct_seconds": round(cold_construct_s, 6),
                "inference_seconds": round(cold_inference_s, 6),
                "total_seconds": round(cold_construct_s + cold_inference_s, 6),
            },
            "retained_model_inference": {
                "trials_seconds": [round(value, 6) for value in retained_inference_seconds],
                **_summary(retained_inference_seconds),
            },
            "reconstruct_per_call": {
                "construct_trials_seconds": [
                    round(value, 6) for value in reconstructed_construct_seconds
                ],
                "inference_trials_seconds": [
                    round(value, 6) for value in reconstructed_inference_seconds
                ],
                "total_trials_seconds": [round(value, 6) for value in reconstructed_total_seconds],
                "construct": _summary(reconstructed_construct_seconds),
                "inference": _summary(reconstructed_inference_seconds),
                "total": _summary(reconstructed_total_seconds),
            },
            "retained_vs_reconstruct": {
                "median_seconds_saved_per_call": round(savings_s, 6),
                "median_speedup": round(speedup, 4) if speedup is not None else None,
            },
        }
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--format", default="m4a")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = benchmark(args.input, args.format, trials=args.trials)
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(output, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)

    if not result["outputs_equivalent"]:
        raise SystemExit("Beat This lifecycle variants changed beat/downbeat output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

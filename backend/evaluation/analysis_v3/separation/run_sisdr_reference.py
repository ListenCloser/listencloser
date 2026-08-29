"""Run the objective BabySlakh SI-SDR gate for source separation.

This is a current-main replay of only the objective reference-quality slice from
historical PR #426. It intentionally does not evaluate beats or transcription.
"""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path
from statistics import mean, median
from typing import Any

from .adapters.demucs import DemucsAdapter
from .datasets.babyslakh_reference import (
    TARGET_STEMS,
    build_reference_stems,
    materialize_tracks,
)
from .metrics.si_sdr import compare_si_sdr_mixture_vs_stem
from .run import _load_audio

DEFAULT_TRACKS = (
    "Track00001",
    "Track00002",
    "Track00003",
    "Track00004",
    "Track00005",
)
DEFAULT_EXCERPT_SECONDS = 30.0


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for stem in TARGET_STEMS:
        deltas = [
            float(row["stems"][stem]["improvement_db"])
            for row in rows
            if row["stems"].get(stem, {}).get("improvement_db") is not None
        ]
        summary[stem] = {
            "scored_tracks": len(deltas),
            "missing_reference_tracks": sum(
                row["stems"].get(stem, {}).get("state") == "missing_reference" for row in rows
            ),
            "missing_estimate_tracks": sum(
                row["stems"].get(stem, {}).get("state") == "missing_estimate" for row in rows
            ),
            "withheld_silent_reference_tracks": sum(
                row["stems"].get(stem, {}).get("state") == "withheld_silent_reference"
                for row in rows
            ),
            "mean_improvement_db": round(mean(deltas), 3) if deltas else None,
            "median_improvement_db": round(median(deltas), 3) if deltas else None,
            "improved_tracks": sum(delta > 0 for delta in deltas),
            "degraded_tracks": sum(delta < 0 for delta in deltas),
        }
    return summary


def run_babyslakh_sisdr_gate(
    *,
    track_ids: tuple[str, ...] = DEFAULT_TRACKS,
    excerpt_seconds: float = DEFAULT_EXCERPT_SECONDS,
    device: str = "cpu",
) -> dict[str, Any]:
    if not track_ids:
        raise ValueError("track_ids must be non-empty")
    if excerpt_seconds <= 0:
        raise ValueError("excerpt_seconds must be positive")

    tracks = materialize_tracks(track_ids)
    separator = DemucsAdapter(device=device)
    separator.load()

    rows: list[dict[str, Any]] = []
    for track_id in track_ids:
        mixture_path, reference_paths, source_counts = build_reference_stems(
            tracks[track_id],
            excerpt_seconds=excerpt_seconds,
        )
        mixture, sample_rate = _load_audio(
            str(mixture_path),
            start=0.0,
            end=excerpt_seconds,
            target_sr=44100,
        )
        separated = separator.separate(mixture, sample_rate)
        if not separated.ok:
            raise RuntimeError(f"HTDemucs failed for {track_id}: {separated.error}")

        stem_results: dict[str, Any] = {}
        for stem in TARGET_STEMS:
            reference_path = reference_paths.get(stem)
            if reference_path is None:
                stem_results[stem] = {"state": "missing_reference"}
                continue
            estimate = separated.get_stem(stem)
            if estimate is None:
                stem_results[stem] = {
                    "state": "missing_estimate",
                    "reference_source_count": source_counts[stem],
                }
                continue

            reference, reference_rate = _load_audio(
                str(reference_path),
                start=0.0,
                end=excerpt_seconds,
                target_sr=44100,
            )
            if reference_rate != sample_rate:
                raise ValueError(
                    f"Reference sample-rate mismatch for {track_id}/{stem}: "
                    f"{reference_rate} != {sample_rate}"
                )
            comparison = compare_si_sdr_mixture_vs_stem(mixture, estimate, reference)
            if comparison is None:
                stem_results[stem] = {
                    "state": "withheld_silent_reference",
                    "reference_source_count": source_counts[stem],
                }
                continue
            stem_results[stem] = {
                "state": "scored",
                "reference_source_count": source_counts[stem],
                **comparison.to_dict(),
            }

        rows.append(
            {
                "id": track_id,
                "excerpt_start_seconds": 0.0,
                "excerpt_end_seconds": excerpt_seconds,
                "stems": stem_results,
            }
        )

    return {
        "experiment": "separation_objective_sisdr_v2",
        "dataset": "BabySlakh",
        "dataset_source": "https://zenodo.org/records/4603870",
        "dataset_license": "CC BY 4.0",
        "selection": f"first {excerpt_seconds:g}s of fixed tracks Track00001-Track00005",
        "reference_kind": "exact isolated source audio grouped into htdemucs stem families",
        "metric": {
            "library": "fast-bss-eval",
            "version": version("fast-bss-eval"),
            "function": "fast_bss_eval.si_sdr",
            "zero_mean": True,
            "clamp_db": 100.0,
            "decision_quantity": "separated_stem_si_sdr_db - mixture_si_sdr_db",
        },
        "separator": {
            "candidate": "HTDemucs",
            "demucs_package_version": version("demucs"),
            "model": "htdemucs",
            "model_signature": "955717e8",
            "inference_shifts": 0,
            "device": device,
        },
        "tracks": list(track_ids),
        "summary": _summarize(rows),
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BabySlakh objective SI-SDR gate")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--excerpt-seconds", type=float, default=DEFAULT_EXCERPT_SECONDS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = run_babyslakh_sisdr_gate(
        device=args.device,
        excerpt_seconds=args.excerpt_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

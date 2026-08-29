"""Run the separation -> beat downstream gate on fixed BabySlakh excerpts.

The reference grid comes from each track's aligned ``all_src.mid`` synthesis
MIDI. This is controlled symbolic/synthesis evidence, not a human-annotated
real-recording beat benchmark.
"""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path
from statistics import mean, median
from typing import Any

import pretty_midi

from evaluation.datasets.babyslakh import BabySlakhAdapter

from .beat_downstream import compare_mixture_vs_drums
from .run import _load_audio

DEFAULT_TRACKS = (
    "Track00001",
    "Track00002",
    "Track00003",
    "Track00004",
    "Track00005",
)
DEFAULT_EXCERPT_SECONDS = 60.0


def _reference_beats(midi_path: str, *, end_seconds: float) -> list[float]:
    if end_seconds <= 0:
        raise ValueError("end_seconds must be positive")
    beats = [
        float(value)
        for value in pretty_midi.PrettyMIDI(midi_path).get_beats()
        if 0.0 <= float(value) < end_seconds
    ]
    if not beats:
        raise ValueError(f"No synthesis beat grid before {end_seconds}s in {midi_path}")
    return beats


def run_babyslakh_beat_gate(
    *,
    track_ids: tuple[str, ...] = DEFAULT_TRACKS,
    excerpt_seconds: float = DEFAULT_EXCERPT_SECONDS,
    device: str = "cpu",
) -> dict[str, Any]:
    if excerpt_seconds <= 0:
        raise ValueError("excerpt_seconds must be positive")

    from .adapters.demucs import DemucsAdapter

    dataset = BabySlakhAdapter()
    separator = DemucsAdapter(device=device)
    separator.load()

    rows: list[dict[str, Any]] = []
    f1_deltas: list[float] = []
    coverage_deltas: list[float] = []

    for track_id in track_ids:
        resolved = dataset.resolve({"source_id": track_id})
        if not resolved.reference_midi_path:
            raise ValueError(f"Missing aligned MIDI for {track_id}")

        mixture, sample_rate = _load_audio(
            resolved.audio_path,
            start=0.0,
            end=excerpt_seconds,
            target_sr=44100,
        )
        separated = separator.separate(mixture, sample_rate)
        if not separated.ok or separated.drums is None:
            raise RuntimeError(f"HTDemucs failed for {track_id}: {separated.error}")

        reference_beats = _reference_beats(
            resolved.reference_midi_path,
            end_seconds=excerpt_seconds,
        )
        comparison = compare_mixture_vs_drums(
            mixture,
            separated.drums,
            sample_rate,
            reference_beats,
        )
        rows.append(
            {
                "id": track_id,
                "excerpt_start_seconds": 0.0,
                "excerpt_end_seconds": excerpt_seconds,
                "reference_beats": len(reference_beats),
                "comparison": comparison.to_dict(),
            }
        )
        f1_deltas.append(comparison.f1_delta)
        coverage_deltas.append(comparison.reference_coverage_delta)

    return {
        "experiment": "separation_to_beat_downstream_v2",
        "dataset": "BabySlakh",
        "dataset_source": "https://zenodo.org/records/4603870",
        "dataset_license": "CC BY 4.0",
        "selection": f"first {excerpt_seconds:g}s of fixed tracks Track00001-Track00005",
        "reference_kind": "symbolic_synthesis_beat_grid_from_all_src_midi",
        "reference_limitation": (
            "Controlled synthetic-mixture evidence; not human-annotated "
            "real-recording generalization."
        ),
        "separator": {
            "candidate": "HTDemucs",
            "demucs_package_version": version("demucs"),
            "model": "htdemucs",
            "model_signature": "955717e8",
            "inference_shifts": 0,
            "device": device,
        },
        "beat_estimator": "production music_features.estimate_beat_grid",
        "metric": "Analysis V3 pulse compute_beat_f1 + compute_event_timing at 70ms",
        "tracks": list(track_ids),
        "summary": {
            "mean_f1_delta": round(mean(f1_deltas), 4),
            "median_f1_delta": round(median(f1_deltas), 4),
            "improved_f1_tracks": sum(value > 0 for value in f1_deltas),
            "degraded_f1_tracks": sum(value < 0 for value in f1_deltas),
            "mean_reference_coverage_delta": round(mean(coverage_deltas), 4),
            "median_reference_coverage_delta": round(median(coverage_deltas), 4),
        },
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BabySlakh separation -> beat gate")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--excerpt-seconds", type=float, default=DEFAULT_EXCERPT_SECONDS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = run_babyslakh_beat_gate(
        device=args.device,
        excerpt_seconds=args.excerpt_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

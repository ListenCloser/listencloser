"""Run the separation -> bass AMT downstream gate on fixed BabySlakh excerpts."""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path
from statistics import mean, median
from typing import Any

from .adapters.demucs import DemucsAdapter
from .bass_amt import compare_mixture_vs_bass_stem
from .datasets.babyslakh_bass import bass_reference_midis, materialize_tracks
from .run import _load_audio

DEFAULT_TRACKS = (
    "Track00001",
    "Track00002",
    "Track00003",
    "Track00004",
    "Track00005",
)
DEFAULT_EXCERPT_SECONDS = 30.0


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row["state"] == "scored"]
    onset_deltas = [float(row["comparison"]["onset_f1_delta"]) for row in scored]
    offset_deltas = [float(row["comparison"]["onset_offset_f1_delta"]) for row in scored]
    return {
        "scored_tracks": len(scored),
        "missing_bass_reference_tracks": sum(
            row["state"] == "missing_bass_reference" for row in rows
        ),
        "no_bass_notes_in_excerpt_tracks": sum(
            row["state"] == "no_bass_notes_in_excerpt" for row in rows
        ),
        "mean_onset_f1_delta": round(mean(onset_deltas), 4) if onset_deltas else None,
        "median_onset_f1_delta": round(median(onset_deltas), 4) if onset_deltas else None,
        "onset_improved_tracks": sum(delta > 0 for delta in onset_deltas),
        "onset_degraded_tracks": sum(delta < 0 for delta in onset_deltas),
        "mean_onset_offset_f1_delta": round(mean(offset_deltas), 4) if offset_deltas else None,
        "median_onset_offset_f1_delta": round(median(offset_deltas), 4) if offset_deltas else None,
    }


def run_babyslakh_bass_amt_gate(
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
        reference_midis = bass_reference_midis(tracks[track_id])
        if not reference_midis:
            rows.append({"id": track_id, "state": "missing_bass_reference"})
            continue

        mixture, sample_rate = _load_audio(
            str(tracks[track_id] / "mix.wav"),
            start=0.0,
            end=excerpt_seconds,
            target_sr=44100,
        )
        separated = separator.separate(mixture, sample_rate)
        if not separated.ok or separated.bass is None:
            raise RuntimeError(f"HTDemucs bass separation failed for {track_id}: {separated.error}")

        try:
            comparison = compare_mixture_vs_bass_stem(
                mixture,
                separated.bass,
                sample_rate,
                reference_midis,
                excerpt_seconds=excerpt_seconds,
            )
        except ValueError as exc:
            if "No bass reference notes" not in str(exc):
                raise
            rows.append(
                {
                    "id": track_id,
                    "state": "no_bass_notes_in_excerpt",
                    "reference_source_count": len(reference_midis),
                }
            )
            continue

        rows.append(
            {
                "id": track_id,
                "state": "scored",
                "excerpt_start_seconds": 0.0,
                "excerpt_end_seconds": excerpt_seconds,
                "reference_source_count": len(reference_midis),
                "comparison": comparison.to_dict(),
            }
        )

    summary = _summary(rows)
    if summary["scored_tracks"] == 0:
        raise ValueError("Fixed BabySlakh subset produced no scorable bass AMT excerpts")

    return {
        "experiment": "separation_to_bass_amt_v2",
        "dataset": "BabySlakh",
        "dataset_source": "https://zenodo.org/records/4603870",
        "dataset_license": "CC BY 4.0",
        "selection": f"first {excerpt_seconds:g}s of fixed tracks Track00001-Track00005",
        "reference_kind": "aligned per-source MIDI whose metadata inst_class contains bass",
        "separator": {
            "candidate": "HTDemucs",
            "demucs_package_version": version("demucs"),
            "model": "htdemucs",
            "model_signature": "955717e8",
            "inference_shifts": 0,
            "device": device,
        },
        "transcription": {
            "engine": "production BasicPitchEngine via run_basic_pitch adapter",
            "library_version": version("basic-pitch"),
            "channel_policy": "both mixture and separated bass folded to mono before Basic Pitch",
        },
        "metric": {
            "primary": "multitrack_transcription.match_notes flat onset F1",
            "secondary": "same matcher with require_offset=True",
            "onset_tolerance_seconds": 0.05,
            "pitch_tolerance_cents": 50.0,
            "offset_ratio": 0.2,
            "offset_min_tolerance_seconds": 0.05,
        },
        "tracks": list(track_ids),
        "summary": summary,
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BabySlakh separation -> bass AMT gate")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--excerpt-seconds", type=float, default=DEFAULT_EXCERPT_SECONDS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = run_babyslakh_bass_amt_gate(
        device=args.device,
        excerpt_seconds=args.excerpt_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

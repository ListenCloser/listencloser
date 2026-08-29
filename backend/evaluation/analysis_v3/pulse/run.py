"""Pulse/beat/tempo/meter evaluation runner.

Usage:
  python -m backend.evaluation.analysis_v3.pulse.run --candidate current
  python -m backend.evaluation.analysis_v3.pulse.run --candidate all
  python -m backend.evaluation.analysis_v3.pulse.run --candidate beat_this --task beat
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np

from .adapters import ADAPTERS, PulseAdapter
from .adapters.base import PulseMetadata
from .metrics import (
    check_determinism,
    compute_beat_f1,
    compute_downbeat_f1,
    compute_tempo_accuracy,
    compute_tempo_error,
    generate_synthetic_audio,
    measure_latency,
)
from .metrics.tempo import TempoResult


def _load_adapter(candidate: str, device: str = "cpu") -> PulseAdapter:
    if candidate not in ADAPTERS:
        raise ValueError(f"Unknown candidate: {candidate}. Available: {list(ADAPTERS.keys())}")
    return ADAPTERS[candidate](device=device)


def _resolve_path(path: str) -> str:
    """Resolve ${VAR}/rest style paths."""
    if path.startswith("${"):
        end = path.find("}")
        if end != -1:
            env_var = path[2:end]
            rest = path[end + 1 :]
            expanded = os.environ.get(env_var, "")
            if expanded:
                return expanded + rest
    return path


def _normalize_dataset_name(name: str) -> str:
    """Normalize dataset identifiers used for provenance checks."""
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def _manifest_dataset_names(manifest: dict[str, Any]) -> list[str]:
    """Return normalized dataset identifiers represented by a manifest."""
    names = {
        _normalize_dataset_name(str(clip["dataset"]))
        for clip in manifest.get("clips", [])
        if clip.get("dataset")
    }
    if not names and manifest.get("dataset"):
        names.add(_normalize_dataset_name(str(manifest["dataset"])))
    return sorted(names)


def _assess_training_overlap(
    metadata: PulseMetadata,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Assess whether evaluation data overlaps a checkpoint's training corpora."""
    datasets = _manifest_dataset_names(manifest)
    training = {_normalize_dataset_name(name) for name in metadata.training_datasets}
    held_out = {_normalize_dataset_name(name) for name in metadata.held_out_datasets}
    overlap = sorted(set(datasets) & training)
    held_out_matches = sorted(set(datasets) & held_out)

    return {
        "datasets": datasets,
        "checkpoint_name": metadata.checkpoint_name,
        "training_overlap": overlap,
        "held_out_matches": held_out_matches,
        "generalization_safe": not overlap,
    }


def _validate_training_overlap(
    metadata: PulseMetadata,
    manifest: dict[str, Any],
    *,
    allow_training_overlap: bool,
) -> dict[str, Any]:
    """Reject silent train/eval overlap unless explicitly requested."""
    assessment = _assess_training_overlap(metadata, manifest)
    if assessment["training_overlap"] and not allow_training_overlap:
        overlap = ", ".join(assessment["training_overlap"])
        checkpoint = metadata.checkpoint_name or metadata.candidate
        raise ValueError(
            f"Refusing to score {checkpoint} on training dataset(s): {overlap}. "
            "Use a held-out/unseen corpus, a checkpoint with a compatible split, "
            "or pass --allow-training-overlap for an explicitly in-sample probe."
        )
    return assessment


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    """Return deterministic descriptive statistics for per-piece metrics."""
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "p25": None,
            "p75": None,
            "max": None,
        }

    array = np.asarray(values, dtype=float)
    return {
        "count": len(values),
        "mean": round(float(np.mean(array)), 4),
        "median": round(float(np.median(array)), 4),
        "min": round(float(np.min(array)), 4),
        "p25": round(float(np.percentile(array, 25)), 4),
        "p75": round(float(np.percentile(array, 75)), 4),
        "max": round(float(np.max(array)), 4),
    }


def _summarize_beat_evaluation(
    results: list[dict[str, Any]],
    beat_f1_values: list[float],
    downbeat_f1_values: list[float],
    tempo_results: list[TempoResult],
) -> dict[str, Any]:
    """Summarize scored pieces without discarding the per-piece evidence."""
    failed = sum(1 for result in results if result.get("error"))
    completed = len(results) - failed
    latency_values = [
        float(result["latency_seconds"])
        for result in results
        if result.get("latency_seconds") is not None
    ]

    return {
        "completed": completed,
        "failed": failed,
        "failure_rate": round(failed / len(results), 4) if results else 0.0,
        "beat_f1": _distribution(beat_f1_values),
        "downbeat_f1": _distribution(downbeat_f1_values),
        "tempo": compute_tempo_accuracy(tempo_results, tolerance_pct=4.0),
        "latency_seconds": _distribution(latency_values),
    }


def _load_audio(
    audio_path: str,
    start: float = 0.0,
    end: float | None = None,
    target_sr: int = 22050,
) -> tuple[np.ndarray, int]:
    """Load audio segment."""
    import soundfile as sf

    info = sf.info(audio_path)
    sr = info.samplerate
    start_sample = int(start * sr)
    end_sample = int(min(end, info.duration) * sr) if end else int(info.duration * sr)

    data, sr = sf.read(
        audio_path,
        start=start_sample,
        stop=end_sample,
        dtype="float32",
    )
    if data.ndim > 1:
        data = data.mean(axis=1)

    if target_sr != sr:
        import torch
        import torchaudio

        waveform = torch.from_numpy(data).float().unsqueeze(0)
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=target_sr)
        data = resampler(waveform).squeeze(0).numpy()
        sr = target_sr

    return data, sr


def _load_annotations(
    annotation_path: str,
) -> dict[str, Any]:
    """Load beat/downbeat annotations."""
    with open(annotation_path) as f:
        return json.load(f)


def run_operational_evaluation(
    candidate: str,
    device: str = "cpu",
) -> dict[str, Any]:
    """Run operational evaluation for a candidate."""
    print(f"\n{'='*60}")
    print(f"Operational evaluation: {candidate}")
    print(f"{'='*60}")

    result: dict[str, Any] = {
        "candidate": candidate,
        "device": device,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "arch": platform.machine(),
    }

    try:
        adapter = _load_adapter(candidate, device)
        meta = adapter.metadata()
        result["engine"] = meta.engine
        result["code_license"] = meta.code_license
        result["checkpoint_license"] = meta.checkpoint_license
        result["checkpoint_name"] = meta.checkpoint_name
        result["training_datasets"] = list(meta.training_datasets)
        result["held_out_datasets"] = list(meta.held_out_datasets)
        result["supports_beats"] = meta.supports_beats
        result["supports_downbeats"] = meta.supports_downbeats
        result["supports_tempo"] = meta.supports_tempo
        result["supports_meter"] = meta.supports_meter
    except Exception as e:
        result["install_success"] = False
        result["install_error"] = str(e)
        return result

    result["install_success"] = True

    try:
        t0 = time.monotonic()
        adapter.load()
        result["load_success"] = True
        result["load_time_seconds"] = round(time.monotonic() - t0, 2)
    except Exception as e:
        result["load_success"] = False
        result["load_error"] = str(e)
        return result

    for duration_label, duration in [("10s", 10.0), ("30s", 30.0)]:
        audio = generate_synthetic_audio(duration_seconds=duration)
        metrics = measure_latency(adapter, audio, 22050, num_runs=3)
        result[f"cpu_latency_{duration_label}"] = {
            "latency_seconds": metrics.latency_seconds,
            "audio_duration_seconds": metrics.audio_duration_seconds,
            "error": metrics.error,
        }

    audio_10s = generate_synthetic_audio(duration_seconds=10.0)
    result["determinism_stable"] = check_determinism(adapter, audio_10s, 22050, num_runs=3)

    return result


def run_beat_evaluation(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
    *,
    allow_training_overlap: bool = False,
) -> dict[str, Any]:
    """Run beat tracking evaluation."""
    print(f"\n{'='*60}")
    print(f"Beat evaluation: {candidate}")
    print(f"{'='*60}")

    with open(manifest_path) as f:
        manifest = json.load(f)

    adapter = _load_adapter(candidate, device)
    metadata = adapter.metadata()
    data_validity = _validate_training_overlap(
        metadata,
        manifest,
        allow_training_overlap=allow_training_overlap,
    )
    adapter.load()

    results: list[dict[str, Any]] = []
    beat_f1_values: list[float] = []
    downbeat_f1_values: list[float] = []
    tempo_results: list[TempoResult] = []
    skipped_missing_audio = 0

    for clip in manifest["clips"]:
        audio_path = _resolve_path(clip["audio_path"])
        if not os.path.exists(audio_path):
            skipped_missing_audio += 1
            print(f"  SKIP {clip['id']}: audio not found at {audio_path}")
            continue

        try:
            audio, sr = _load_audio(audio_path, target_sr=22050)
            pulse_result = adapter.analyze(audio, sr)

            if not pulse_result.ok:
                results.append(
                    {
                        "id": clip["id"],
                        "error": pulse_result.error,
                    }
                )
                print(f"  FAILED {clip['id']}: {pulse_result.error}")
                continue

            beat_f1 = None
            downbeat_f1 = None
            tempo_result = None

            if "reference_beats" in clip:
                beat_f1 = compute_beat_f1(
                    pulse_result.beats,
                    clip["reference_beats"],
                    tolerance=0.07,
                )
                beat_f1_values.append(beat_f1.f1)

            if "reference_downbeats" in clip and pulse_result.downbeats:
                downbeat_f1 = compute_downbeat_f1(
                    pulse_result.downbeats,
                    clip["reference_downbeats"],
                    tolerance=0.07,
                )
                downbeat_f1_values.append(downbeat_f1.f1)

            if "reference_bpm" in clip:
                tempo_result = compute_tempo_error(
                    pulse_result.tempo_bpm,
                    clip["reference_bpm"],
                )
                tempo_results.append(tempo_result)

            results.append(
                {
                    "id": clip["id"],
                    "beat_f1": beat_f1.to_dict() if beat_f1 else None,
                    "downbeat_f1": downbeat_f1.to_dict() if downbeat_f1 else None,
                    "tempo": tempo_result.to_dict() if tempo_result else None,
                    "predicted_beats": len(pulse_result.beats),
                    "predicted_downbeats": len(pulse_result.downbeats),
                    "latency_seconds": pulse_result.latency_seconds,
                }
            )
            print(f"  OK {clip['id']}: beats={len(pulse_result.beats)}")

        except Exception as e:
            results.append({"id": clip["id"], "error": str(e)})
            print(f"  FAILED {clip['id']}: {e}")

    return {
        "candidate": candidate,
        "task": "beat",
        "data_validity": data_validity,
        "num_manifest_clips": len(manifest["clips"]),
        "num_clips": len(results),
        "num_skipped_missing_audio": skipped_missing_audio,
        "summary": _summarize_beat_evaluation(
            results,
            beat_f1_values,
            downbeat_f1_values,
            tempo_results,
        ),
        "results": results,
    }


def run_candidate(
    candidate: str,
    task: str = "all",
    manifest_dir: str | None = None,
    device: str = "cpu",
    output_dir: str = "results",
    *,
    allow_training_overlap: bool = False,
) -> dict[str, Any]:
    """Run evaluation for a candidate."""
    if manifest_dir is None:
        manifest_dir = str(Path(__file__).parent / "manifests")

    results: dict[str, Any] = {
        "candidate": candidate,
        "task": task,
        "device": device,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if task in ("all", "operational"):
        results["operational"] = run_operational_evaluation(candidate, device)

    if task in ("all", "beat"):
        manifest_path = os.path.join(manifest_dir, "diversity_probe.json")
        if os.path.exists(manifest_path):
            results["beat"] = run_beat_evaluation(
                candidate,
                manifest_path,
                device,
                allow_training_overlap=allow_training_overlap,
            )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{candidate}.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Pulse evaluation runner")
    parser.add_argument(
        "--candidate",
        required=True,
        choices=list(ADAPTERS.keys()) + ["all"],
        help="Candidate to evaluate",
    )
    parser.add_argument(
        "--task",
        default="all",
        choices=["all", "operational", "beat"],
        help="Evaluation task",
    )
    parser.add_argument(
        "--manifest-dir",
        default=None,
        help="Directory containing manifests",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "mps"],
        help="Device",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory",
    )
    parser.add_argument(
        "--allow-training-overlap",
        action="store_true",
        help="Allow explicitly in-sample evaluation on checkpoint training datasets",
    )
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = str(Path(__file__).parent / "results")

    if args.candidate == "all":
        for candidate in ADAPTERS:
            try:
                run_candidate(
                    candidate,
                    args.task,
                    args.manifest_dir,
                    args.device,
                    args.output_dir,
                    allow_training_overlap=args.allow_training_overlap,
                )
            except Exception as e:
                print(f"\nFAILED {candidate}: {e}")
    else:
        run_candidate(
            args.candidate,
            args.task,
            args.manifest_dir,
            args.device,
            args.output_dir,
            allow_training_overlap=args.allow_training_overlap,
        )


if __name__ == "__main__":
    main()

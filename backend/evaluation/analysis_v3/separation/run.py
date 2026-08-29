"""Source separation evaluation runner.

Usage:
  python -m backend.evaluation.analysis_v3.separation.run --candidate bs_roformer
  python -m backend.evaluation.analysis_v3.separation.run --candidate all
  python -m backend.evaluation.analysis_v3.separation.run --candidate demucs --task operational
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .adapters import ADAPTERS, SeparationAdapter
from .metrics import (
    check_determinism,
    compare_bass_note_f1_mixture_vs_stem,
    compare_beat_f1_mixture_vs_stem,
    compare_si_sdr_mixture_vs_stem,
    generate_synthetic_audio,
    measure_latency,
)


def _load_adapter(candidate: str, device: str = "cpu") -> SeparationAdapter:
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


def _load_audio(
    audio_path: str,
    start: float = 0.0,
    end: float | None = None,
    target_sr: int = 44100,
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


def _summarize_deltas(values: list[float], digits: int = 4) -> dict[str, Any]:
    return {
        "mean": round(float(np.mean(values)), digits),
        "median": round(float(np.median(values)), digits),
        "improved": sum(delta > 0 for delta in values),
        "degraded": sum(delta < 0 for delta in values),
        "unchanged": sum(delta == 0 for delta in values),
    }


def _error_text(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"


def _result_filename(candidate: str, task: str, manifest_name: str | None) -> str:
    parts = [candidate, task]
    if manifest_name:
        parts.append(manifest_name)
    raw = "-".join(parts).lower()
    slug = "".join(character if character.isalnum() else "-" for character in raw)
    slug = "-".join(part for part in slug.split("-") if part)
    return f"{slug[:120]}.json"


def run_operational_evaluation(
    candidate: str,
    device: str = "cpu",
) -> dict[str, Any]:
    """Run operational evaluation for a candidate."""
    print(f"\n{'=' * 60}")
    print(f"Operational evaluation: {candidate}")
    print(f"{'=' * 60}")

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
        result["model_id"] = meta.model_id
        result["code_license"] = meta.code_license
        result["weight_license"] = meta.weight_license
        result["num_stems"] = meta.num_stems
        result["supports_vocals"] = meta.supports_vocals
        result["supports_drums"] = meta.supports_drums
        result["supports_bass"] = meta.supports_bass
        result["supports_other"] = meta.supports_other
    except Exception as error:
        result["install_success"] = False
        result["install_error"] = _error_text(error)
        return result

    result["install_success"] = True

    try:
        started = time.monotonic()
        adapter.load()
        result["load_success"] = True
        result["load_time_seconds"] = round(time.monotonic() - started, 2)
        result["provenance"] = asdict(adapter.metadata())
    except Exception as error:
        result["load_success"] = False
        result["load_error"] = _error_text(error)
        return result

    for duration_label, duration in [("10s", 10.0), ("30s", 30.0), ("3min", 180.0)]:
        audio = generate_synthetic_audio(duration_seconds=duration)
        is_long_probe = duration >= 180
        metrics = measure_latency(
            adapter,
            audio,
            44100,
            num_runs=1 if is_long_probe else 2,
            warmup_runs=0 if is_long_probe else 1,
        )
        result[f"latency_{duration_label}"] = {
            "latency_seconds": metrics.latency_seconds,
            "latency_min": metrics.latency_min,
            "latency_max": metrics.latency_max,
            "latency_p95": metrics.latency_p95,
            "real_time_factor": metrics.real_time_factor,
            "audio_duration_seconds": metrics.audio_duration_seconds,
            "process_max_rss_mb": metrics.process_max_rss_mb,
            "cuda_peak_allocated_mb": metrics.cuda_peak_allocated_mb,
            "error": metrics.error,
        }

    audio_10s = generate_synthetic_audio(duration_seconds=10.0)
    result["determinism_stable"] = check_determinism(adapter, audio_10s, 44100, num_runs=2)
    return result


def run_separation_evaluation(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
    *,
    with_bass_amt: bool = False,
) -> dict[str, Any]:
    """Run separation, objective quality, and available downstream comparisons."""
    print(f"\n{'=' * 60}")
    print(f"Separation evaluation: {candidate}")
    print(f"{'=' * 60}")

    with open(manifest_path) as handle:
        manifest = json.load(handle)
    clips = manifest.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError("Separation manifest requires a non-empty clips list")

    adapter = _load_adapter(candidate, device)
    adapter.load()
    candidate_provenance = asdict(adapter.metadata())

    results: list[dict[str, Any]] = []
    beat_deltas: list[float] = []
    bass_amt_deltas: list[float] = []
    quality_deltas: dict[str, list[float]] = {}
    downstream_scored_clip_ids: set[str] = set()
    beat_scored_clips = 0
    bass_amt_scored_clips = 0
    bass_amt_missing_references = 0
    objective_scored_stems = 0
    objective_missing_references = 0
    objective_task_failures = 0
    downstream_task_failures = 0
    missing_audio_clips = 0
    separation_failed_clips = 0
    separation_succeeded_clips = 0

    for clip in clips:
        clip_id = str(clip.get("id") or "unknown")
        source_audio_path = str(clip.get("audio_path") or "")
        audio_path = _resolve_path(source_audio_path)
        if not audio_path or not os.path.exists(audio_path):
            missing_audio_clips += 1
            results.append(
                {
                    "id": clip_id,
                    "status": "skipped_missing_audio",
                    "audio_path": source_audio_path,
                }
            )
            print(f"  SKIP {clip_id}: audio not found at {audio_path}")
            continue

        try:
            audio, sr = _load_audio(audio_path, target_sr=44100)
            started = time.monotonic()
            sep_result = adapter.separate(audio, sr)
            separation_latency = time.monotonic() - started
        except Exception as error:
            separation_failed_clips += 1
            results.append(
                {
                    "id": clip_id,
                    "status": "failed_separation",
                    "error": _error_text(error),
                }
            )
            print(f"  FAILED {clip_id}: {error}")
            continue

        if not sep_result.ok:
            separation_failed_clips += 1
            results.append(
                {
                    "id": clip_id,
                    "status": "failed_separation",
                    "error": sep_result.error,
                    "latency_seconds": round(separation_latency, 4),
                }
            )
            print(f"  FAILED {clip_id}: {sep_result.error}")
            continue

        separation_succeeded_clips += 1
        stem_metrics: dict[str, Any] = {}
        for stem_name in ["vocals", "drums", "bass", "other"]:
            stem = sep_result.get_stem(stem_name)
            if stem is not None:
                stem_metrics[stem_name] = {
                    "shape": list(stem.shape),
                    "duration_seconds": round(stem.shape[-1] / sr, 2),
                }

        objective_quality: dict[str, Any] = {}
        objective_errors: dict[str, str] = {}
        reference_stems = clip.get("reference_stems") or {}
        for stem_name, reference_path_value in reference_stems.items():
            estimated_stem = sep_result.get_stem(stem_name)
            if estimated_stem is None:
                objective_task_failures += 1
                objective_errors[stem_name] = "candidate did not emit requested stem"
                continue

            reference_path = _resolve_path(str(reference_path_value))
            if not os.path.exists(reference_path):
                objective_missing_references += 1
                objective_errors[stem_name] = f"reference not found: {reference_path_value}"
                continue

            try:
                reference_stem, reference_sr = _load_audio(reference_path, target_sr=sr)
                if reference_sr != sr:
                    raise RuntimeError(
                        f"reference resample mismatch: {reference_sr} != {sr}"
                    )
                quality_comparison = compare_si_sdr_mixture_vs_stem(
                    audio,
                    estimated_stem,
                    reference_stem,
                )
                if quality_comparison is None:
                    raise ValueError("SI-SDR comparison was unscored")
            except Exception as error:
                objective_task_failures += 1
                objective_errors[stem_name] = _error_text(error)
                continue

            objective_quality[stem_name] = quality_comparison.to_dict()
            quality_deltas.setdefault(stem_name, []).append(quality_comparison.improvement_db)
            objective_scored_stems += 1

        downstream: dict[str, Any] = {}
        downstream_errors: dict[str, str] = {}

        reference_beats = clip.get("reference_beats")
        if reference_beats:
            drums = sep_result.get_stem("drums")
            if drums is None:
                downstream_task_failures += 1
                downstream_errors["beat_f1_drums"] = "candidate did not emit drums stem"
            else:
                try:
                    beat_comparison = compare_beat_f1_mixture_vs_stem(
                        audio,
                        drums,
                        sr,
                        reference_beats,
                    )
                    if beat_comparison is None:
                        raise ValueError("beat comparison was unscored")
                except Exception as error:
                    downstream_task_failures += 1
                    downstream_errors["beat_f1_drums"] = _error_text(error)
                else:
                    downstream["beat_f1_drums"] = beat_comparison.to_dict()
                    beat_deltas.append(beat_comparison.delta)
                    beat_scored_clips += 1
                    downstream_scored_clip_ids.add(clip_id)

        if with_bass_amt:
            bass_reference_values = (clip.get("reference_midis") or {}).get("bass") or []
            if bass_reference_values:
                bass = sep_result.get_stem("bass")
                if bass is None:
                    downstream_task_failures += 1
                    downstream_errors["bass_note_f1"] = "candidate did not emit bass stem"
                else:
                    bass_reference_paths = [
                        Path(_resolve_path(str(value))) for value in bass_reference_values
                    ]
                    missing_bass_references = [
                        path for path in bass_reference_paths if not path.is_file()
                    ]
                    if missing_bass_references:
                        bass_amt_missing_references += len(missing_bass_references)
                        downstream_errors["bass_note_f1"] = (
                            "missing reference MIDI: "
                            + ", ".join(str(path) for path in missing_bass_references)
                        )
                    else:
                        try:
                            bass_comparison = compare_bass_note_f1_mixture_vs_stem(
                                audio,
                                bass,
                                sr,
                                bass_reference_paths,
                            )
                            if bass_comparison is None:
                                raise ValueError("bass AMT comparison was unscored")
                        except Exception as error:
                            downstream_task_failures += 1
                            downstream_errors["bass_note_f1"] = _error_text(error)
                        else:
                            downstream["bass_note_f1"] = bass_comparison.to_dict()
                            bass_amt_deltas.append(bass_comparison.delta)
                            bass_amt_scored_clips += 1
                            downstream_scored_clip_ids.add(clip_id)

        row: dict[str, Any] = {
            "id": clip_id,
            "status": "ok",
            "stems": stem_metrics,
            "latency_seconds": round(separation_latency, 4),
        }
        if sep_result.metadata:
            row["separation_metadata"] = sep_result.metadata
        if objective_quality:
            row["objective_quality"] = objective_quality
        if objective_errors:
            row["objective_errors"] = objective_errors
        if downstream:
            row["downstream"] = downstream
        if downstream_errors:
            row["downstream_errors"] = downstream_errors
        results.append(row)
        print(f"  OK {clip_id}: stems={list(stem_metrics.keys())}")

    summary: dict[str, Any] = {
        "manifest_clips": len(clips),
        "separation_succeeded_clips": separation_succeeded_clips,
        "separation_failed_clips": separation_failed_clips,
        "missing_audio_clips": missing_audio_clips,
        "downstream_scored_clips": len(downstream_scored_clip_ids),
        "beat_scored_clips": beat_scored_clips,
        "bass_amt_scored_clips": bass_amt_scored_clips,
        "bass_amt_missing_references": bass_amt_missing_references,
        "downstream_task_failures": downstream_task_failures,
        "objective_scored_stems": objective_scored_stems,
        "objective_missing_references": objective_missing_references,
        "objective_task_failures": objective_task_failures,
    }
    if beat_deltas:
        summary["beat_f1_drums_delta"] = _summarize_deltas(beat_deltas)
    if bass_amt_deltas:
        summary["bass_note_f1_delta"] = _summarize_deltas(bass_amt_deltas)
    if quality_deltas:
        summary["si_sdr_improvement_db_by_stem"] = {
            stem_name: _summarize_deltas(deltas, digits=3)
            for stem_name, deltas in sorted(quality_deltas.items())
        }

    return {
        "candidate": candidate,
        "task": "separation",
        "manifest": manifest.get("name", Path(manifest_path).name),
        "manifest_path": manifest_path,
        "dataset": manifest.get("dataset"),
        "dataset_license": manifest.get("dataset_license") or manifest.get("license"),
        "candidate_provenance": candidate_provenance,
        "num_clips": len(results),
        "summary": summary,
        "results": results,
    }


def run_candidate(
    candidate: str,
    task: str = "all",
    manifest_dir: str | None = None,
    manifest_path: str | None = None,
    device: str = "cpu",
    output_dir: str = "results",
    *,
    with_bass_amt: bool = False,
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

    if task in ("all", "separation"):
        selected_manifest = manifest_path or os.path.join(manifest_dir, "diversity_probe.json")
        if os.path.exists(selected_manifest):
            results["separation"] = run_separation_evaluation(
                candidate,
                selected_manifest,
                device,
                with_bass_amt=with_bass_amt,
            )
        else:
            results["separation"] = {
                "candidate": candidate,
                "task": "separation",
                "manifest_path": selected_manifest,
                "error": "manifest not found",
            }

    os.makedirs(output_dir, exist_ok=True)
    separation = results.get("separation")
    manifest_name = separation.get("manifest") if isinstance(separation, dict) else None
    output_name = _result_filename(candidate, task, manifest_name)
    output_path = os.path.join(output_dir, output_name)
    with open(output_path, "w") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Source separation evaluation runner")
    parser.add_argument(
        "--candidate",
        required=True,
        choices=list(ADAPTERS.keys()) + ["all"],
        help="Candidate to evaluate",
    )
    parser.add_argument(
        "--task",
        default="all",
        choices=["all", "operational", "separation"],
        help="Evaluation task",
    )
    parser.add_argument(
        "--manifest-dir",
        default=None,
        help="Directory containing manifests",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "Explicit manifest path. Annotated manifests may include reference_beats, "
            "reference_stems, and reference_midis."
        ),
    )
    parser.add_argument(
        "--with-bass-amt",
        action="store_true",
        help="Also run production Basic Pitch on mixture vs bass stem when bass MIDI exists.",
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
                    args.manifest,
                    args.device,
                    args.output_dir,
                    with_bass_amt=args.with_bass_amt,
                )
            except Exception as error:
                print(f"\nFAILED {candidate}: {error}")
    else:
        run_candidate(
            args.candidate,
            args.task,
            args.manifest_dir,
            args.manifest,
            args.device,
            args.output_dir,
            with_bass_amt=args.with_bass_amt,
        )


if __name__ == "__main__":
    main()

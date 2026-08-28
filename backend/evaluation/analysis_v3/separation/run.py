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
from pathlib import Path
from typing import Any

import numpy as np

from .adapters import ADAPTERS, SeparationAdapter
from .metrics import (
    check_determinism,
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
        result["model_id"] = meta.model_id
        result["code_license"] = meta.code_license
        result["weight_license"] = meta.weight_license
        result["num_stems"] = meta.num_stems
        result["supports_vocals"] = meta.supports_vocals
        result["supports_drums"] = meta.supports_drums
        result["supports_bass"] = meta.supports_bass
        result["supports_other"] = meta.supports_other
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
        metrics = measure_latency(adapter, audio, 44100, num_runs=2)
        result[f"cpu_latency_{duration_label}"] = {
            "latency_seconds": metrics.latency_seconds,
            "audio_duration_seconds": metrics.audio_duration_seconds,
            "error": metrics.error,
        }

    audio_10s = generate_synthetic_audio(duration_seconds=10.0)
    result["determinism_stable"] = check_determinism(adapter, audio_10s, 44100, num_runs=2)

    return result


def run_separation_evaluation(
    candidate: str,
    manifest_path: str,
    device: str = "cpu",
) -> dict[str, Any]:
    """Run separation evaluation on manifest clips."""
    print(f"\n{'='*60}")
    print(f"Separation evaluation: {candidate}")
    print(f"{'='*60}")

    with open(manifest_path) as f:
        manifest = json.load(f)

    adapter = _load_adapter(candidate, device)
    adapter.load()

    results: list[dict[str, Any]] = []
    for clip in manifest["clips"]:
        audio_path = _resolve_path(clip["audio_path"])
        if not os.path.exists(audio_path):
            print(f"  SKIP {clip['id']}: audio not found at {audio_path}")
            continue

        try:
            audio, sr = _load_audio(audio_path, target_sr=44100)
            sep_result = adapter.separate(audio, sr)

            if not sep_result.ok:
                results.append(
                    {
                        "id": clip["id"],
                        "error": sep_result.error,
                    }
                )
                print(f"  FAILED {clip['id']}: {sep_result.error}")
                continue

            stem_metrics: dict[str, Any] = {}
            for stem_name in ["vocals", "drums", "bass", "other"]:
                stem = sep_result.get_stem(stem_name)
                if stem is not None:
                    stem_metrics[stem_name] = {
                        "shape": list(stem.shape),
                        "duration_seconds": round(stem.shape[-1] / sr, 2),
                    }

            results.append(
                {
                    "id": clip["id"],
                    "stems": stem_metrics,
                    "latency_seconds": sep_result.latency_seconds,
                }
            )
            print(f"  OK {clip['id']}: stems={list(stem_metrics.keys())}")

        except Exception as e:
            results.append({"id": clip["id"], "error": str(e)})
            print(f"  FAILED {clip['id']}: {e}")

    return {
        "candidate": candidate,
        "task": "separation",
        "num_clips": len(results),
        "results": results,
    }


def run_candidate(
    candidate: str,
    task: str = "all",
    manifest_dir: str | None = None,
    device: str = "cpu",
    output_dir: str = "results",
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
        manifest_path = os.path.join(manifest_dir, "diversity_probe.json")
        if os.path.exists(manifest_path):
            results["separation"] = run_separation_evaluation(candidate, manifest_path, device)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{candidate}.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
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
                run_candidate(candidate, args.task, args.manifest_dir, args.device, args.output_dir)
            except Exception as e:
                print(f"\nFAILED {candidate}: {e}")
    else:
        run_candidate(args.candidate, args.task, args.manifest_dir, args.device, args.output_dir)


if __name__ == "__main__":
    main()

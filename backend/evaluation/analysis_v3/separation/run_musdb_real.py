"""Held-out real-recording separation gate on the official MUSDB18 7s preview.

Research-only. The preview audio is downloaded at evaluation time and is never
committed or uploaded as an artifact; only machine-readable metrics are kept.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

MODEL_NAME = "htdemucs"
MODEL_SIGNATURE = "955717e8"
HF_REPO_ID = "adefossez/HTDemucs"
HF_WEIGHT_FILENAME = "955717e8.safetensors"
HF_WEIGHT_SHA256 = "d9fa14133cfcc034a6758923bb3a8ca9f8dfd0b582134643bbf83f72c17576dd"
MUSDB_SAMPLE_URL = (
    "https://github.com/sigsep/sigsep-mus-db/releases/download/"
    "v0.4.0/MUSDB18-7-STEMS.zip"
)
STEMS = ("drums", "bass", "other", "vocals")
SAMPLE_RATE = 44100
TORCH_NUM_THREADS = 2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_weight_path() -> tuple[Path, dict[str, Any]]:
    from huggingface_hub import hf_hub_download

    started = time.monotonic()
    path = Path(hf_hub_download(repo_id=HF_REPO_ID, filename=HF_WEIGHT_FILENAME))
    actual_sha256 = _sha256(path)
    if actual_sha256 != HF_WEIGHT_SHA256:
        raise RuntimeError(
            "HTDemucs weight SHA256 mismatch: "
            f"expected {HF_WEIGHT_SHA256}, got {actual_sha256}"
        )
    return path, {
        "repository": HF_REPO_ID,
        "filename": HF_WEIGHT_FILENAME,
        "sha256": actual_sha256,
        "size_mb": round(path.stat().st_size / (1024.0 * 1024.0), 2),
        "download_seconds": round(time.monotonic() - started, 3),
        "verification": "sha256_fail_closed",
    }


def _load_model(weight_path: Path, *, device: str):
    from demucs.apply import BagOfModels
    from demucs.hf import load_safetensors_model

    model = BagOfModels([load_safetensors_model(weight_path)])
    model.eval()
    model.to(device)
    return model


def _channel_first(audio: np.ndarray) -> np.ndarray:
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        return array[None, :]
    if array.ndim != 2:
        raise ValueError(f"expected mono/stereo audio, got shape {array.shape}")
    if array.shape[0] <= 2 and array.shape[1] > array.shape[0]:
        return array
    if array.shape[1] <= 2 and array.shape[0] > array.shape[1]:
        return array.T
    raise ValueError(f"ambiguous channel layout {array.shape}")


def _si_sdr_mean(reference: np.ndarray, estimate: np.ndarray) -> float | None:
    """Channel-wise standardized SI-SDR, withholding silent references."""
    import fast_bss_eval

    ref = _channel_first(reference)
    est = _channel_first(estimate)
    length = min(ref.shape[-1], est.shape[-1])
    ref = ref[..., :length]
    est = est[..., :length]

    if ref.shape[0] != est.shape[0]:
        ref = np.mean(ref, axis=0, keepdims=True)
        est = np.mean(est, axis=0, keepdims=True)

    scores: list[float] = []
    for channel in range(ref.shape[0]):
        ref_channel = ref[channel]
        if np.max(np.abs(ref_channel)) < 1e-7:
            continue
        score = fast_bss_eval.si_sdr(
            ref_channel[None, :],
            est[channel][None, :],
            zero_mean=True,
            clamp_db=100.0,
        )
        scores.append(float(np.asarray(score).reshape(-1)[0]))
    return float(np.mean(scores)) if scores else None


def _separate(model: Any, mixture: np.ndarray, *, device: str) -> dict[str, np.ndarray]:
    import torch
    from demucs.apply import apply_model

    audio = _channel_first(mixture)
    if audio.shape[0] == 1:
        audio = np.repeat(audio, 2, axis=0)
    waveform = torch.from_numpy(audio).float().unsqueeze(0).to(device)
    with torch.no_grad():
        sources = apply_model(model, waveform, device=device, shifts=0)
    if sources.dim() == 4:
        sources = sources.squeeze(0)
    source_names = list(model.sources)
    return {
        name: sources[index].detach().cpu().numpy()
        for index, name in enumerate(source_names)
        if name in STEMS
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for stem in STEMS:
        deltas = [
            float(row["delta_si_sdr_db"])
            for row in rows
            if row.get("stem") == stem and row.get("status") == "scored"
        ]
        if not deltas:
            summary[stem] = {"scored": 0}
            continue
        summary[stem] = {
            "scored": len(deltas),
            "mean_delta_si_sdr_db": round(statistics.fmean(deltas), 4),
            "median_delta_si_sdr_db": round(statistics.median(deltas), 4),
            "min_delta_si_sdr_db": round(min(deltas), 4),
            "max_delta_si_sdr_db": round(max(deltas), 4),
            "improved": sum(delta > 0.0 for delta in deltas),
            "degraded": sum(delta < 0.0 for delta in deltas),
            "unchanged": sum(delta == 0.0 for delta in deltas),
        }
    return summary


def run(*, device: str = "cpu", max_tracks: int | None = None) -> dict[str, Any]:
    if device != "cpu":
        raise ValueError("This held-out gate is intentionally CPU-only")

    import musdb
    import torch

    torch.set_num_threads(TORCH_NUM_THREADS)
    weight_path, weight_metadata = _verified_weight_path()
    model = _load_model(weight_path, device=device)

    dataset_started = time.monotonic()
    database = musdb.DB(download=True, subsets="test")
    tracks = list(database.tracks)
    if max_tracks is not None:
        tracks = tracks[:max_tracks]

    rows: list[dict[str, Any]] = []
    track_failures: list[dict[str, str]] = []
    for track in tracks:
        track_name = str(track.name)
        try:
            mixture = np.asarray(track.audio, dtype=np.float32)
            sample_rate = int(track.rate)
            if sample_rate != SAMPLE_RATE:
                raise ValueError(f"expected {SAMPLE_RATE} Hz, got {sample_rate}")
            separated = _separate(model, mixture, device=device)
        except Exception as exc:  # pragma: no cover - real-data/inference boundary
            track_failures.append(
                {"track": track_name, "error": f"{type(exc).__name__}: {exc}"}
            )
            continue

        for stem in STEMS:
            try:
                reference = np.asarray(track.targets[stem].audio, dtype=np.float32)
                estimate = separated.get(stem)
                if estimate is None:
                    rows.append({"track": track_name, "stem": stem, "status": "missing_estimate"})
                    continue
                mixture_score = _si_sdr_mean(reference, mixture)
                stem_score = _si_sdr_mean(reference, estimate)
                if mixture_score is None or stem_score is None:
                    rows.append({"track": track_name, "stem": stem, "status": "withheld_silent_reference"})
                    continue
                rows.append(
                    {
                        "track": track_name,
                        "stem": stem,
                        "status": "scored",
                        "mixture_si_sdr_db": round(mixture_score, 4),
                        "stem_si_sdr_db": round(stem_score, 4),
                        "delta_si_sdr_db": round(stem_score - mixture_score, 4),
                    }
                )
            except Exception as exc:  # pragma: no cover - real-data boundary
                rows.append(
                    {
                        "track": track_name,
                        "stem": stem,
                        "status": "failed_metric",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    return {
        "experiment": "separation_musdb18_real_recording_v1",
        "question": (
            "Does the objective HTDemucs stem-quality gain observed on synthetic mixtures "
            "survive on held-out real MUSDB18 recordings?"
        ),
        "dataset": {
            "name": "MUSDB18 7-second preview",
            "subset": "test",
            "access": "musdb.DB(download=True, subsets='test')",
            "sample_url": MUSDB_SAMPLE_URL,
            "usage_terms": "audio restricted to academic purposes per musdb documentation",
            "audio_committed_or_uploaded": False,
            "available_test_tracks": len(database.tracks),
            "evaluated_tracks": len(tracks),
            "download_and_eval_seconds": round(time.monotonic() - dataset_started, 3),
        },
        "candidate": {
            "name": "HTDemucs",
            "demucs_version": version("demucs"),
            "model": MODEL_NAME,
            "model_signature": MODEL_SIGNATURE,
            "inference_shifts": 0,
            "torch_version": torch.__version__,
            "torch_num_threads": torch.get_num_threads(),
            "device": device,
            "weight_artifact": weight_metadata,
        },
        "metric": {
            "name": "SI-SDR gain over mixture baseline",
            "implementation": "fast_bss_eval.si_sdr",
            "zero_mean": True,
            "clamp_db": 100.0,
            "stereo_policy": "score channels independently and average; withhold silent reference channels",
        },
        "rows": rows,
        "summary": _summarize(rows),
        "track_failures": track_failures,
        "success": bool(rows) and not track_failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run held-out MUSDB18 real-recording separation gate")
    parser.add_argument("--device", choices=["cpu"], default="cpu")
    parser.add_argument("--max-tracks", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = run(device=args.device, max_tracks=args.max_tracks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    if not payload["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

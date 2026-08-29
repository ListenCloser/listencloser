"""Measure MR-MT3 process-per-track versus persistent-model CPU runtime.

Research-only follow-up for #337. The quality decision remains owned by the
canonical decoder-sidecar result in ``slakh_redux_subset_results.json``. This
module asks only whether the expensive stock CLI timings are mostly repeated
process/model-load overhead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

TRACK_IDS = (
    "Track01876",
    "Track01877",
    "Track01878",
    "Track01880",
    "Track01881",
)
SEGMENT_SECONDS = 30.0
MIRROR_REPO_ID = "J1mmymm/MIMuT_Data_v2"
MIRROR_REVISION = "bb320faf307f5d24aeced0e60f9445ff0abce205"
UPSTREAM_DATASET_SOURCE = "https://zenodo.org/records/4599666"
UPSTREAM_DATASET_LICENSE = "CC BY 4.0"
MT3_INFER_REVISION = "2d20ee5bb6ca727968bd23c6100fd2a35154166b"
MT3_INFER_VERSION = "0.2.0"
MR_MT3_CHECKPOINT_SHA256 = "b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f"
EXPECTED_CROPPED_MIX_SHA256 = {
    "Track01876": "b7f3a32155a14e7a2e8ea3c8d46e4fd924384d28f20de214945302004a236d9a",
    "Track01877": "620b11c7bc00e494d609d9145a715927cf0b429dc865af73d37bee67e1a9b1d4",
    "Track01878": "f2f54d66c5a1ab9ec430b8571f7fff0c7498dc4343bb1f820dd8cfe1483c0923",
    "Track01880": "9c632afea1f59ac23cb032d8340a096076504dabdb7d0ce8995faea9ead036f4",
    "Track01881": "6762066f29458258d56b86c02f2bdbda3c713d60ea92d0526b51f227eaced992",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mirror_url(track_id: str) -> str:
    relative = f"data/Slakh2100_redux/test/{track_id}/mix.flac"
    encoded = quote(relative, safe="/")
    return (
        f"https://huggingface.co/datasets/{MIRROR_REPO_ID}/resolve/" f"{MIRROR_REVISION}/{encoded}"
    )


def _download(url: str, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "hello-ai-analysis-v3-evaluation/1.0"})
    started = time.perf_counter()
    with urlopen(request, timeout=180) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    return {
        "bytes": destination.stat().st_size,
        "sha256": sha256(destination),
        "download_seconds": round(time.perf_counter() - started, 3),
    }


def _crop_first_30_seconds(source: Path, destination: Path) -> float:
    import soundfile as sf

    audio, sample_rate = sf.read(str(source), always_2d=False)
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    end_frame = min(len(audio), int(round(float(sample_rate) * SEGMENT_SECONDS)))
    if end_frame <= 0:
        raise ValueError(f"empty source audio: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(destination), audio[:end_frame], int(sample_rate))
    return end_frame / float(sample_rate)


def prepare_audio(output_root: Path) -> dict[str, Any]:
    """Acquire the same five Slakh excerpts used by the canonical quality run."""
    source_root = output_root / "source"
    audio_root = output_root / "audio"
    entries: list[dict[str, Any]] = []

    for track_id in TRACK_IDS:
        source = source_root / track_id / "mix.flac"
        download = _download(_mirror_url(track_id), source)
        cropped = audio_root / track_id / "mix.wav"
        duration = _crop_first_30_seconds(source, cropped)
        actual_hash = sha256(cropped)
        expected_hash = EXPECTED_CROPPED_MIX_SHA256[track_id]
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"cropped audio hash mismatch for {track_id}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        entries.append(
            {
                "id": track_id,
                "audio": str(cropped.relative_to(output_root)),
                "duration_seconds": round(duration, 3),
                "cropped_sha256": actual_hash,
                "source_download": download,
            }
        )

    payload = {
        "dataset": "Slakh2100-redux",
        "split": "test",
        "upstream": UPSTREAM_DATASET_SOURCE,
        "license": UPSTREAM_DATASET_LICENSE,
        "acquisition_mirror": MIRROR_REPO_ID,
        "mirror_revision": MIRROR_REVISION,
        "selection": list(TRACK_IDS),
        "segment_start_seconds": 0.0,
        "segment_duration_seconds": SEGMENT_SECONDS,
        "audio_committed_or_uploaded": False,
        "entries": entries,
    }
    validate_prepared_manifest(payload)
    manifest_path = output_root / "audio_manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def validate_prepared_manifest(payload: dict[str, Any]) -> None:
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != len(TRACK_IDS):
        raise ValueError("runtime audio manifest must contain the fixed five tracks")
    ids = [entry.get("id") for entry in entries]
    if ids != list(TRACK_IDS):
        raise ValueError(f"unexpected runtime track order: {ids}")
    for entry in entries:
        track_id = str(entry["id"])
        if entry.get("cropped_sha256") != EXPECTED_CROPPED_MIX_SHA256[track_id]:
            raise ValueError(f"runtime audio hash does not match canonical quality run: {track_id}")


def _max_rss_mb() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return value / (1024.0 * 1024.0)
    return value / 1024.0


def _midi_semantic_sha256(path: Path) -> str:
    """Hash non-meta MIDI events using absolute ticks, independent of file bytes."""
    import mido

    midi = mido.MidiFile(str(path))
    normalized: list[dict[str, Any]] = []
    for track_index, track in enumerate(midi.tracks):
        absolute_tick = 0
        for message in track:
            absolute_tick += int(message.time)
            if message.is_meta:
                continue
            values = message.dict()
            values.pop("time", None)
            normalized.append(
                {
                    "track": track_index,
                    "tick": absolute_tick,
                    **values,
                }
            )
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _count_note_ons(path: Path) -> int:
    import mido

    midi = mido.MidiFile(str(path))
    return sum(
        1
        for track in midi.tracks
        for message in track
        if message.type == "note_on" and int(message.velocity) > 0
    )


def _run_cli_control(
    manifest: dict[str, Any],
    *,
    output_root: Path,
    mt3_binary: Path,
) -> list[dict[str, Any]]:
    control_root = output_root / "cli_control"
    control_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for entry in manifest["entries"]:
        track_id = str(entry["id"])
        audio_path = output_root / str(entry["audio"])
        midi_path = control_root / f"{track_id}.mid"
        time_path = control_root / f"{track_id}.time"
        log_path = control_root / f"{track_id}.log"
        command = [
            "/usr/bin/time",
            "-f",
            "%M",
            "-o",
            str(time_path),
            str(mt3_binary),
            "transcribe",
            str(audio_path),
            "-o",
            str(midi_path),
            "-m",
            "mr_mt3",
            "--device",
            "cpu",
            "--no-download",
        ]
        started = time.perf_counter()
        process = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            env=os.environ.copy(),
        )
        runtime = time.perf_counter() - started
        log_path.write_text(process.stdout or "")
        if process.returncode != 0:
            raise RuntimeError(f"MR-MT3 CLI control failed for {track_id}; see {log_path}")
        if not midi_path.is_file():
            raise RuntimeError(f"MR-MT3 CLI control produced no MIDI for {track_id}")
        peak_rss_kib = int(time_path.read_text().strip())
        rows.append(
            {
                "id": track_id,
                "runtime_seconds": round(runtime, 3),
                "rtf": round(runtime / float(entry["duration_seconds"]), 4),
                "process_max_rss_mb": round(peak_rss_kib / 1024.0, 2),
                "midi_sha256": sha256(midi_path),
                "midi_semantic_sha256": _midi_semantic_sha256(midi_path),
                "note_ons": _count_note_ons(midi_path),
            }
        )
    return rows


def _persistent_model_run(
    manifest: dict[str, Any],
    *,
    output_root: Path,
    checkpoint_path: Path,
    control_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    import importlib.metadata as metadata

    import torch
    from mt3_infer import load_model
    from mt3_infer.utils.audio import load_audio

    package_version = metadata.version("mt3-infer")
    if package_version != MT3_INFER_VERSION:
        raise RuntimeError(
            f"unexpected mt3-infer version: expected {MT3_INFER_VERSION}, got {package_version}"
        )
    actual_checkpoint_hash = sha256(checkpoint_path)
    if actual_checkpoint_hash != MR_MT3_CHECKPOINT_SHA256:
        raise RuntimeError(
            "MR-MT3 checkpoint hash mismatch: "
            f"expected {MR_MT3_CHECKPOINT_SHA256}, got {actual_checkpoint_hash}"
        )

    started = time.perf_counter()
    model = load_model(
        "mr_mt3",
        checkpoint_path=str(checkpoint_path),
        device="cpu",
        cache=True,
        auto_download=False,
    )
    model_load_seconds = time.perf_counter() - started
    model_metadata = {
        "load_seconds": round(model_load_seconds, 3),
        "process_max_rss_mb_after_load": round(_max_rss_mb(), 2),
        "torch_version": torch.__version__,
        "torch_num_threads": torch.get_num_threads(),
        "mt3_infer_version": package_version,
        "mt3_infer_revision": MT3_INFER_REVISION,
        "checkpoint_sha256": actual_checkpoint_hash,
        "checkpoint_bytes": checkpoint_path.stat().st_size,
    }

    persistent_root = output_root / "persistent"
    persistent_root.mkdir(parents=True, exist_ok=True)
    controls = {row["id"]: row for row in control_rows}
    rows: list[dict[str, Any]] = []

    for entry in manifest["entries"]:
        track_id = str(entry["id"])
        audio_path = output_root / str(entry["audio"])
        output_midi = persistent_root / f"{track_id}.mid"
        started = time.perf_counter()
        audio, sample_rate = load_audio(str(audio_path))
        midi = model.transcribe(audio, sr=sample_rate)
        midi.save(str(output_midi))
        runtime = time.perf_counter() - started
        semantic_hash = _midi_semantic_sha256(output_midi)
        note_ons = _count_note_ons(output_midi)
        control = controls[track_id]
        rows.append(
            {
                "id": track_id,
                "runtime_seconds": round(runtime, 3),
                "rtf": round(runtime / float(entry["duration_seconds"]), 4),
                "process_max_rss_mb_cumulative": round(_max_rss_mb(), 2),
                "midi_sha256": sha256(output_midi),
                "midi_semantic_sha256": semantic_hash,
                "note_ons": note_ons,
                "matches_cli_semantics": semantic_hash == control["midi_semantic_sha256"],
                "matches_cli_note_count": note_ons == control["note_ons"],
            }
        )

    repeat_entry = manifest["entries"][0]
    repeat_audio, repeat_sr = load_audio(str(output_root / str(repeat_entry["audio"])))
    repeat_path = persistent_root / f"{repeat_entry['id']}.repeat.mid"
    started = time.perf_counter()
    repeat_midi = model.transcribe(repeat_audio, sr=repeat_sr)
    repeat_midi.save(str(repeat_path))
    repeat_seconds = time.perf_counter() - started
    first_row = rows[0]
    repeat_semantic_hash = _midi_semantic_sha256(repeat_path)
    repeat = {
        "id": repeat_entry["id"],
        "runtime_seconds": round(repeat_seconds, 3),
        "midi_semantic_sha256": repeat_semantic_hash,
        "matches_first_persistent_semantics": (
            repeat_semantic_hash == first_row["midi_semantic_sha256"]
        ),
        "note_ons": _count_note_ons(repeat_path),
    }
    return model_metadata, rows, repeat


def summarize_comparison(
    control_rows: list[dict[str, Any]],
    persistent_rows: list[dict[str, Any]],
    *,
    model_load_seconds: float,
) -> dict[str, Any]:
    controls = {row["id"]: row for row in control_rows}
    persistent = {row["id"]: row for row in persistent_rows}
    if set(controls) != set(persistent):
        raise ValueError("control and persistent rows must cover the same tracks")

    paired: list[dict[str, Any]] = []
    for track_id in TRACK_IDS:
        control_seconds = float(controls[track_id]["runtime_seconds"])
        persistent_seconds = float(persistent[track_id]["runtime_seconds"])
        paired.append(
            {
                "id": track_id,
                "cli_process_seconds": control_seconds,
                "persistent_seconds": persistent_seconds,
                "speedup": round(control_seconds / persistent_seconds, 4),
            }
        )

    control_times = [float(row["runtime_seconds"]) for row in control_rows]
    persistent_times = [float(row["runtime_seconds"]) for row in persistent_rows]
    speedups = [float(row["speedup"]) for row in paired]
    return {
        "paired": paired,
        "cli_mean_seconds": round(statistics.fmean(control_times), 3),
        "cli_median_seconds": round(statistics.median(control_times), 3),
        "persistent_mean_seconds": round(statistics.fmean(persistent_times), 3),
        "persistent_median_seconds": round(statistics.median(persistent_times), 3),
        "mean_speedup": round(statistics.fmean(speedups), 4),
        "median_speedup": round(statistics.median(speedups), 4),
        "cli_total_seconds": round(sum(control_times), 3),
        "persistent_model_load_seconds": round(model_load_seconds, 3),
        "persistent_five_track_inference_seconds": round(sum(persistent_times), 3),
        "persistent_load_plus_five_tracks_seconds": round(
            model_load_seconds + sum(persistent_times), 3
        ),
        "all_cli_semantics_equal": all(
            bool(row["matches_cli_semantics"]) for row in persistent_rows
        ),
        "all_cli_note_counts_equal": all(
            bool(row["matches_cli_note_count"]) for row in persistent_rows
        ),
    }


def benchmark(
    *,
    manifest_path: Path,
    output_root: Path,
    mt3_binary: Path,
    checkpoint_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    validate_prepared_manifest(manifest)
    checkpoint_path = checkpoint_root / "mr_mt3" / "mt3.pth"
    if not checkpoint_path.is_file():
        raise RuntimeError(f"missing prefetched MR-MT3 checkpoint: {checkpoint_path}")

    control_rows = _run_cli_control(
        manifest,
        output_root=output_root,
        mt3_binary=mt3_binary,
    )
    model_metadata, persistent_rows, repeat = _persistent_model_run(
        manifest,
        output_root=output_root,
        checkpoint_path=checkpoint_path,
        control_rows=control_rows,
    )
    comparison = summarize_comparison(
        control_rows,
        persistent_rows,
        model_load_seconds=float(model_metadata["load_seconds"]),
    )
    success = (
        bool(comparison["all_cli_semantics_equal"])
        and bool(comparison["all_cli_note_counts_equal"])
        and bool(repeat["matches_first_persistent_semantics"])
    )
    payload = {
        "experiment": "analysis_v3_mr_mt3_persistent_runtime_v1",
        "question": (
            "How much of stock process-per-track MR-MT3 CPU cost is repeated process/model "
            "load overhead versus one resident model reused across requests?"
        ),
        "scope": (
            "operational evidence only; canonical quality remains the #404 " "decoder-sidecar run"
        ),
        "dataset": manifest,
        "candidate": {
            "name": "MR-MT3",
            "runner": "mt3-infer",
            "runner_version": MT3_INFER_VERSION,
            "runner_revision": MT3_INFER_REVISION,
            "checkpoint_sha256": MR_MT3_CHECKPOINT_SHA256,
            "device": "cpu",
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "control": {
            "topology": "one mt3-infer CLI process per track; checkpoint already prefetched",
            "rows": control_rows,
        },
        "persistent": {
            "topology": "one process; load_model('mr_mt3') once; reuse model for all tracks",
            "model": model_metadata,
            "rows": persistent_rows,
            "repeat_first_track": repeat,
        },
        "comparison": comparison,
        "success": success,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    if not success:
        raise RuntimeError("persistent runtime parity gate failed; result written for diagnosis")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="MR-MT3 persistent CPU runtime evaluation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--output-root", type=Path, required=True)

    benchmark_parser = subparsers.add_parser("benchmark")
    benchmark_parser.add_argument("--manifest", type=Path, required=True)
    benchmark_parser.add_argument("--output-root", type=Path, required=True)
    benchmark_parser.add_argument("--mt3-binary", type=Path, required=True)
    benchmark_parser.add_argument("--checkpoint-root", type=Path, required=True)
    benchmark_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        payload = prepare_audio(args.output_root)
    else:
        payload = benchmark(
            manifest_path=args.manifest,
            output_root=args.output_root,
            mt3_binary=args.mt3_binary,
            checkpoint_root=args.checkpoint_root,
            output_path=args.output,
        )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

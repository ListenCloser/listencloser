"""Program-preserving five-track Slakh2100 Redux evaluation for #337.

This reruns the exact selective Redux acquisition and Basic Pitch baseline from
``slakh_redux_subset_run.py`` but executes MR-MT3 through the pinned adapter's
model/preprocess/forward/codec decoder while replacing only mt3-infer 0.2.0's
lossy final MIDI serializer. The serializer loss is documented in
``mr_mt3_program_preserving_runner.py``.

Scientific validity check: flat MR-MT3 note metrics from this run must match the
preceding lossy-CLI run on the same five cropped excerpts. If they do not, the
program-preserving path must not be used for instrument-aware conclusions.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from evaluation.analysis_v3.multitrack_transcription.run import (
    run_basic_pitch_baseline,
    score_model_run,
)
from evaluation.analysis_v3.multitrack_transcription.slakh_redux_subset_run import (
    MIRROR_REPO_ID,
    MIRROR_REVISION,
    MR_MT3_CHECKPOINT_SHA256,
    MT3_INFER_SOURCE_REVISION,
    SEGMENT_DURATION_SECONDS,
    SEGMENT_START_SECONDS,
    TRACK_IDS,
    UPSTREAM_DATASET_LICENSE,
    UPSTREAM_DATASET_SOURCE,
    acquire_track,
    prepare_mr_mt3_checkpoint,
    sha256,
)

SERIALIZER_NAME = "hello-ai research program-preserving serializer"


def run_program_preserving_batch(
    *,
    mt3_python: Path,
    checkpoint: Path,
    dataset_root: Path,
    output_root: Path,
) -> dict[str, object]:
    mt3_root = output_root / "mr_mt3"
    mt3_root.mkdir(parents=True, exist_ok=True)
    jobs_path = mt3_root / "jobs.json"
    stats_path = mt3_root / "program_preserving_stats.json"
    time_path = mt3_root / "batch.time"
    log_path = mt3_root / "batch.log"
    runner_path = Path(__file__).with_name("mr_mt3_program_preserving_runner.py").resolve()

    jobs = [
        {
            "id": track_id,
            "audio": str((dataset_root / track_id / "mix.wav").resolve()),
            "output": str((mt3_root / f"{track_id}.mid").resolve()),
        }
        for track_id in TRACK_IDS
    ]
    jobs_path.write_text(json.dumps(jobs, indent=2) + "\n")

    command = [
        "/usr/bin/time",
        "-f",
        "%M",
        "-o",
        str(time_path),
        str(mt3_python),
        str(runner_path),
        "--checkpoint",
        str(checkpoint),
        "--jobs-json",
        str(jobs_path),
        "--stats",
        str(stats_path),
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
    elapsed = time.perf_counter() - started
    log_path.write_text(process.stdout or "")
    if process.returncode != 0:
        raise RuntimeError(f"program-preserving MR-MT3 batch failed; see {log_path}")
    if not stats_path.is_file():
        raise RuntimeError("program-preserving runner produced no stats")

    stats = json.loads(stats_path.read_text())
    tracks = stats.get("tracks")
    if not isinstance(tracks, list) or len(tracks) != len(TRACK_IDS):
        raise RuntimeError("program-preserving runner returned incomplete track stats")
    peak_rss_kib = int(time_path.read_text().strip())
    return {
        "wall_seconds": round(elapsed, 3),
        "batch_process_max_rss_mb": round(peak_rss_kib / 1024.0, 2),
        "stats": stats,
    }


def main() -> None:
    output_root = Path(os.environ.get("MULTITRACK_SMOKE_OUTPUT", "slakh-preserving-output")).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    source_root = Path(os.environ.get("SLAKH_SOURCE_CACHE", output_root / "source-cache")).resolve()
    dataset_root = output_root / "dataset"
    dataset_root.mkdir(parents=True, exist_ok=True)

    acquisition_started = time.perf_counter()
    acquired = [acquire_track(track_id, source_root, dataset_root) for track_id in TRACK_IDS]
    acquisition_seconds = time.perf_counter() - acquisition_started
    manifest = {
        "name": "slakh2100-redux-selective-mirror-5x30s",
        "split": "test",
        "selection": "lexicographically first five visible Redux test tracks; first 30 seconds",
        "limit": len(TRACK_IDS),
        "dataset_license": UPSTREAM_DATASET_LICENSE,
        "dataset_source": UPSTREAM_DATASET_SOURCE,
        "acquisition_mirror": f"https://huggingface.co/datasets/{MIRROR_REPO_ID}",
        "acquisition_mirror_revision": MIRROR_REVISION,
        "ground_truth": "active per-source MIDI/SXX.mid files marked midi_saved=true in metadata.yaml",
        "entries": [item["manifest_entry"] for item in acquired],
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest_hash = sha256(manifest_path)
    acquisition_payload = {
        "mirror_repo_id": MIRROR_REPO_ID,
        "mirror_revision": MIRROR_REVISION,
        "upstream_dataset_source": UPSTREAM_DATASET_SOURCE,
        "upstream_dataset_license": UPSTREAM_DATASET_LICENSE,
        "selection": list(TRACK_IDS),
        "segment_start_seconds": SEGMENT_START_SECONDS,
        "segment_duration_seconds": SEGMENT_DURATION_SECONDS,
        "total_download_and_crop_seconds": round(acquisition_seconds, 3),
        "tracks": [item["acquisition"] for item in acquired],
    }
    (output_root / "acquisition.json").write_text(json.dumps(acquisition_payload, indent=2) + "\n")

    hello_ai_sha = os.environ["HELLO_AI_MEASUREMENT_SHA"]
    basic_root = output_root / "basic_pitch"
    basic_run = run_basic_pitch_baseline(
        manifest_path,
        dataset_root=dataset_root,
        output_dir=basic_root,
        hello_ai_sha=hello_ai_sha,
    )
    basic_run_path = basic_root / "model_run.json"
    basic_run_path.write_text(json.dumps(basic_run, indent=2) + "\n")
    basic_score = score_model_run(manifest_path, basic_run_path, dataset_root=dataset_root)
    (basic_root / "score.json").write_text(json.dumps(basic_score, indent=2) + "\n")

    mt3_binary = Path(os.environ["MT3_INFER_BIN"]).resolve()
    mt3_python = Path(os.environ["MT3_PYTHON_BIN"]).resolve()
    if not mt3_binary.is_file() or not mt3_python.is_file():
        raise RuntimeError("pinned MR-MT3 executable/python missing")
    checkpoint_root = Path(os.environ["MT3_CHECKPOINT_DIR"]).resolve()
    checkpoint_metadata = prepare_mr_mt3_checkpoint(mt3_binary, checkpoint_root, output_root)
    checkpoint_path = checkpoint_root / str(checkpoint_metadata["path"])
    if checkpoint_metadata["sha256"] != MR_MT3_CHECKPOINT_SHA256:
        raise RuntimeError("MR-MT3 checkpoint provenance mismatch")

    batch = run_program_preserving_batch(
        mt3_python=mt3_python,
        checkpoint=checkpoint_path,
        dataset_root=dataset_root,
        output_root=output_root,
    )
    stats = batch["stats"]
    track_stats = {str(item["id"]): item for item in stats["tracks"]}
    if set(track_stats) != set(TRACK_IDS):
        raise RuntimeError("program-preserving runner track IDs do not match fixed selection")

    mt3_root = output_root / "mr_mt3"
    mt3_entries: list[dict[str, object]] = []
    for track_id in TRACK_IDS:
        item = track_stats[track_id]
        predicted_midi = mt3_root / f"{track_id}.mid"
        if not predicted_midi.is_file():
            raise RuntimeError(f"missing program-preserving MIDI for {track_id}")
        runtime_seconds = float(item["audio_load_seconds"]) + float(item["inference_decode_seconds"])
        mt3_entries.append(
            {
                "id": track_id,
                "predicted_midi": predicted_midi.name,
                "runtime_seconds": round(runtime_seconds, 3),
                "process_max_rss_mb": None,
            }
        )

    mt3_version = os.environ["MT3_INFER_VERSION"]
    mt3_torch_version = os.environ["MT3_TORCH_VERSION"]
    mt3_run = {
        "evaluation_id": "analysis_v3_multitrack_slakh_redux_subset_mr_mt3_program_preserving",
        "hello_ai_sha": hello_ai_sha,
        "candidate": "mr_mt3_via_mt3_infer_program_preserving",
        "candidate_revision": (
            f"mt3-infer=={mt3_version}@{MT3_INFER_SOURCE_REVISION}; backend=mr_mt3"
        ),
        "model_checksum": checkpoint_metadata["sha256"],
        "dataset_manifest": {"path": str(manifest_path), "sha256": manifest_hash},
        "code_license": "MIT (mt3-infer / vendored MR-MT3 adapter); serializer is evaluation-only hello-ai code",
        "weight_license": "MIT per gudgud1014/MR-MT3 model repository metadata",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "device": "cpu",
            "mt3_infer": mt3_version,
            "mt3_runner_torch": mt3_torch_version,
            "mt3_runner_executable": str(mt3_binary),
            "serializer": SERIALIZER_NAME,
            "model_load_seconds": stats["model_load_seconds"],
            "batch_wall_seconds": batch["wall_seconds"],
            "batch_process_max_rss_mb": batch["batch_process_max_rss_mb"],
        },
        "runner_source_revision": MT3_INFER_SOURCE_REVISION,
        "checkpoint_files": [checkpoint_metadata],
        "entries": mt3_entries,
    }
    mt3_run_path = mt3_root / "model_run.json"
    mt3_run_path.write_text(json.dumps(mt3_run, indent=2) + "\n")
    mt3_score = score_model_run(manifest_path, mt3_run_path, dataset_root=dataset_root)
    (mt3_root / "score.json").write_text(json.dumps(mt3_score, indent=2) + "\n")

    summary = {
        "scope": "small_decisive_protocol_subset_program_preserving",
        "adoption_eligible": False,
        "reason": "Five 30-second test excerpts establish a real per-source signal, not a final production adoption decision.",
        "scientific_validity_gate": (
            "Flat MR-MT3 note metrics must match the preceding lossy-CLI run exactly; only then may program-aware metrics be interpreted."
        ),
        "tracks": list(TRACK_IDS),
        "segment_seconds": SEGMENT_DURATION_SECONDS,
        "hello_ai_measurement_sha": hello_ai_sha,
        "dataset": {
            "name": manifest["name"],
            "upstream_source": UPSTREAM_DATASET_SOURCE,
            "license": UPSTREAM_DATASET_LICENSE,
            "mirror_repo_id": MIRROR_REPO_ID,
            "mirror_revision": MIRROR_REVISION,
            "manifest_sha256": manifest_hash,
        },
        "basic_pitch": {
            "macro_f1": basic_score["macro_f1"],
            "runtime_seconds_by_track": {
                entry["id"]: entry["runtime_seconds"] for entry in basic_run["entries"]
            },
        },
        "mr_mt3": {
            "macro_f1": mt3_score["macro_f1"],
            "checkpoint": checkpoint_metadata,
            "serializer": SERIALIZER_NAME,
            "model_load_seconds": stats["model_load_seconds"],
            "batch_wall_seconds": batch["wall_seconds"],
            "batch_process_max_rss_mb": batch["batch_process_max_rss_mb"],
            "tracks": stats["tracks"],
        },
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

"""One-off BabySlakh smoke runner for #337 research infrastructure.

This file lives only on the throwaway research-run branch. BabySlakh uses the
combined ``all_src.mid`` reference, so results are exploratory and MUST NOT be
used for an ADOPT decision. The decisive #337 benchmark remains per-source
Slakh2100-redux.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

import pretty_midi
import soundfile as sf

from evaluation.analysis_v3.multitrack_transcription.run import (
    run_basic_pitch_baseline,
    score_model_run,
)
from evaluation.datasets.babyslakh import BabySlakhAdapter

TRACK_ID = "Track00001"
DURATION_SECONDS = 30.0
MT3_INFER_SOURCE_REVISION = "2d20ee5bb6ca727968bd23c6100fd2a35154166b"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def combined_checkpoint_hash(root: Path) -> tuple[str, list[dict[str, object]]]:
    files: list[dict[str, object]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        files.append(
            {
                "path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest(), files


def child_max_rss_mb() -> float:
    value = float(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    return round(value / 1024.0, 2)


def crop_reference(source: Path, output: Path, duration: float) -> int:
    reference = pretty_midi.PrettyMIDI(str(source))
    cropped = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    note_count = 0
    for instrument in reference.instruments:
        target = pretty_midi.Instrument(
            program=instrument.program,
            is_drum=instrument.is_drum,
            name=instrument.name,
        )
        for note in instrument.notes:
            if note.start >= duration or note.end <= 0:
                continue
            target.notes.append(
                pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=max(0.0, note.start),
                    end=min(duration, note.end),
                )
            )
            note_count += 1
        if target.notes:
            cropped.instruments.append(target)
    cropped.write(str(output))
    return note_count


def main() -> None:
    output_root = Path(os.environ.get("MULTITRACK_SMOKE_OUTPUT", "smoke-output")).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    resolved = BabySlakhAdapter().resolve({"source_id": TRACK_ID})
    source_audio = Path(resolved.audio_path)
    source_midi = Path(resolved.reference_midi_path)

    dataset_root = output_root / "dataset"
    track_root = dataset_root / TRACK_ID
    track_root.mkdir(parents=True, exist_ok=True)
    mix_path = track_root / "mix.wav"
    reference_path = track_root / "all_src.mid"

    audio, sr = sf.read(str(source_audio), always_2d=False)
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    frames = min(len(audio), int(round(float(sr) * DURATION_SECONDS)))
    sf.write(str(mix_path), audio[:frames], int(sr))
    actual_duration = frames / float(sr)
    reference_notes = crop_reference(source_midi, reference_path, actual_duration)

    manifest = {
        "name": "babyslakh-exploratory-combined-midi",
        "split": "fixed",
        "selection": f"{TRACK_ID} first {actual_duration:.3f}s",
        "dataset_license": "CC BY 4.0",
        "ground_truth": "BabySlakh all_src.mid combined MIDI; exploratory only",
        "entries": [
            {
                "id": TRACK_ID,
                "mix": f"{TRACK_ID}/mix.wav",
                "reference_midis": [f"{TRACK_ID}/all_src.mid"],
                "mix_sha256": sha256(mix_path),
                "reference_midi_sha256": {
                    f"{TRACK_ID}/all_src.mid": sha256(reference_path)
                },
            }
        ],
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

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
    basic_score = score_model_run(
        manifest_path,
        basic_run_path,
        dataset_root=dataset_root,
    )
    (basic_root / "score.json").write_text(json.dumps(basic_score, indent=2) + "\n")

    mt3_root = output_root / "mr_mt3"
    mt3_root.mkdir(parents=True, exist_ok=True)
    mt3_midi = mt3_root / f"{TRACK_ID}.mid"
    mt3_log = mt3_root / "runner.log"

    started = time.perf_counter()
    process = subprocess.run(
        [
            "mt3-infer",
            "transcribe",
            str(mix_path),
            "-o",
            str(mt3_midi),
            "-m",
            "mr_mt3",
            "--device",
            "cpu",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    elapsed = time.perf_counter() - started
    mt3_log.write_text(process.stdout or "")
    if process.returncode != 0:
        raise RuntimeError(
            f"mt3-infer exited {process.returncode}; see {mt3_log}"
        )
    if not mt3_midi.is_file():
        raise RuntimeError("mt3-infer completed without producing MIDI")

    checkpoint_root = Path(os.environ["MT3_CHECKPOINT_DIR"])
    checkpoint_hash, checkpoint_files = combined_checkpoint_hash(checkpoint_root)
    mt3_run = {
        "evaluation_id": "analysis_v3_multitrack_babyslakh_smoke_mr_mt3",
        "hello_ai_sha": hello_ai_sha,
        "candidate": "mr_mt3_via_mt3_infer",
        "candidate_revision": (
            f"mt3-infer=={version('mt3-infer')}@{MT3_INFER_SOURCE_REVISION}; backend=mr_mt3"
        ),
        "model_checksum": checkpoint_hash,
        "dataset_manifest": {
            "path": str(manifest_path),
            "sha256": sha256(manifest_path),
        },
        "code_license": "MIT (mt3-infer; MR-MT3 vendored code per runner LICENSE)",
        "weight_license": "MIT per gudgud1014/MR-MT3 model repository metadata",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "device": "cpu",
            "mt3_infer": version("mt3-infer"),
        },
        "runner_source_revision": MT3_INFER_SOURCE_REVISION,
        "checkpoint_files": checkpoint_files,
        "entries": [
            {
                "id": TRACK_ID,
                "predicted_midi": mt3_midi.name,
                "runtime_seconds": round(elapsed, 3),
                "process_max_rss_mb": child_max_rss_mb(),
            }
        ],
    }
    mt3_run_path = mt3_root / "model_run.json"
    mt3_run_path.write_text(json.dumps(mt3_run, indent=2) + "\n")
    mt3_score = score_model_run(
        manifest_path,
        mt3_run_path,
        dataset_root=dataset_root,
    )
    (mt3_root / "score.json").write_text(json.dumps(mt3_score, indent=2) + "\n")

    summary = {
        "scope": "exploratory_smoke_only",
        "adoption_eligible": False,
        "reason": (
            "BabySlakh combined all_src.mid is not the decisive per-source "
            "Slakh2100-redux ground-truth protocol"
        ),
        "track_id": TRACK_ID,
        "duration_seconds": round(actual_duration, 3),
        "reference_notes": reference_notes,
        "hello_ai_measurement_sha": hello_ai_sha,
        "basic_pitch": {
            "macro_f1": basic_score["macro_f1"],
            "runtime_seconds": basic_run["entries"][0]["runtime_seconds"],
            "process_max_rss_mb": basic_run["entries"][0]["process_max_rss_mb"],
        },
        "mr_mt3": {
            "macro_f1": mt3_score["macro_f1"],
            "runtime_seconds": mt3_run["entries"][0]["runtime_seconds"],
            "process_max_rss_mb": mt3_run["entries"][0]["process_max_rss_mb"],
            "checkpoint_combined_sha256": checkpoint_hash,
        },
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

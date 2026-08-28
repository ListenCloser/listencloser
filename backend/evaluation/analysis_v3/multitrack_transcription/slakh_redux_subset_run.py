"""Pinned selective Slakh2100-redux subset runner for #337.

This file is intentionally isolated on the research-run branch. It downloads a
small deterministic set of original-structure Slakh2100 Redux test tracks from
an immutable Hugging Face mirror snapshot, crops audio and the exact per-source
MIDI to the same fixed window, and scores hello-ai Basic Pitch vs MR-MT3 through
the frozen #376 evaluator.

The mirror is an acquisition path only. Dataset identity/license remain the
upstream Slakh2100 Redux release (Zenodo 4599666, CC BY 4.0), and all downloaded
bytes are checksummed in the result for reproducibility.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import pretty_midi
import soundfile as sf
import yaml

from evaluation.analysis_v3.multitrack_transcription.run import (
    run_basic_pitch_baseline,
    score_model_run,
)

TRACK_IDS = (
    "Track01876",
    "Track01877",
    "Track01878",
    "Track01880",
    "Track01881",
)
SEGMENT_START_SECONDS = 0.0
SEGMENT_DURATION_SECONDS = 30.0
MIRROR_REPO_ID = "J1mmymm/MIMuT_Data_v2"
MIRROR_REVISION = "bb320faf307f5d24aeced0e60f9445ff0abce205"
UPSTREAM_DATASET_SOURCE = "https://zenodo.org/records/4599666"
UPSTREAM_DATASET_LICENSE = "CC BY 4.0"
MT3_INFER_SOURCE_REVISION = "2d20ee5bb6ca727968bd23c6100fd2a35154166b"
MR_MT3_CHECKPOINT_SHA256 = "b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mirror_url(relative_path: str) -> str:
    encoded = quote(relative_path, safe="/")
    return (
        f"https://huggingface.co/datasets/{MIRROR_REPO_ID}/resolve/"
        f"{MIRROR_REVISION}/{encoded}"
    )


def download(relative_path: str, destination: Path) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        _mirror_url(relative_path),
        headers={"User-Agent": "hello-ai-analysis-v3-evaluation/1.0"},
    )
    started = time.perf_counter()
    with urlopen(request, timeout=180) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    elapsed = time.perf_counter() - started
    return {
        "mirror_path": relative_path,
        "bytes": destination.stat().st_size,
        "sha256": sha256(destination),
        "download_seconds": round(elapsed, 3),
    }


def crop_audio(source: Path, destination: Path) -> float:
    audio, sample_rate = sf.read(str(source), always_2d=False)
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    start_frame = max(0, int(round(float(sample_rate) * SEGMENT_START_SECONDS)))
    end_frame = min(
        len(audio),
        start_frame + int(round(float(sample_rate) * SEGMENT_DURATION_SECONDS)),
    )
    if end_frame <= start_frame:
        raise ValueError(f"empty audio crop for {source}")
    segment = audio[start_frame:end_frame]
    sf.write(str(destination), segment, int(sample_rate))
    return len(segment) / float(sample_rate)


def crop_midi(source: Path, destination: Path, duration: float) -> int:
    reference = pretty_midi.PrettyMIDI(str(source))
    cropped = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    note_count = 0
    start = SEGMENT_START_SECONDS
    end = start + duration
    for instrument in reference.instruments:
        target = pretty_midi.Instrument(
            program=int(instrument.program),
            is_drum=bool(instrument.is_drum),
            name=instrument.name,
        )
        for note in instrument.notes:
            if note.start >= end or note.end <= start:
                continue
            clipped_start = max(start, float(note.start)) - start
            clipped_end = min(end, float(note.end)) - start
            if clipped_end <= clipped_start:
                continue
            target.notes.append(
                pretty_midi.Note(
                    velocity=int(note.velocity),
                    pitch=int(note.pitch),
                    start=clipped_start,
                    end=clipped_end,
                )
            )
            note_count += 1
        if target.notes:
            cropped.instruments.append(target)
    if note_count:
        destination.parent.mkdir(parents=True, exist_ok=True)
        cropped.write(str(destination))
    return note_count


def acquire_track(track_id: str, source_root: Path, dataset_root: Path) -> dict[str, object]:
    prefix = f"data/Slakh2100_redux/test/{track_id}"
    source_track = source_root / track_id
    source_track.mkdir(parents=True, exist_ok=True)

    metadata_path = source_track / "metadata.yaml"
    mix_source = source_track / "mix.flac"
    metadata_download = download(f"{prefix}/metadata.yaml", metadata_path)
    mix_download = download(f"{prefix}/mix.flac", mix_source)

    metadata = yaml.safe_load(metadata_path.read_text())
    stems = metadata.get("stems") if isinstance(metadata, dict) else None
    if not isinstance(stems, dict):
        raise ValueError(f"missing stems metadata for {track_id}")
    midi_source_ids = sorted(
        source_id
        for source_id, details in stems.items()
        if isinstance(details, dict) and details.get("midi_saved") is True
    )
    if not midi_source_ids:
        raise ValueError(f"no midi_saved sources for {track_id}")

    raw_midis: list[dict[str, object]] = []
    raw_midi_paths: list[tuple[str, Path]] = []
    for source_id in midi_source_ids:
        midi_path = source_track / "MIDI" / f"{source_id}.mid"
        raw_midis.append(download(f"{prefix}/MIDI/{source_id}.mid", midi_path))
        raw_midi_paths.append((source_id, midi_path))

    target_track = dataset_root / track_id
    target_track.mkdir(parents=True, exist_ok=True)
    target_mix = target_track / "mix.wav"
    duration = crop_audio(mix_source, target_mix)

    reference_midis: list[str] = []
    cropped_midi_hashes: dict[str, str] = {}
    active_sources: list[dict[str, object]] = []
    total_reference_notes = 0
    for source_id, raw_path in raw_midi_paths:
        target_midi = target_track / "MIDI" / f"{source_id}.mid"
        note_count = crop_midi(raw_path, target_midi, duration)
        if not note_count:
            continue
        relative = str(target_midi.relative_to(dataset_root))
        reference_midis.append(relative)
        cropped_midi_hashes[relative] = sha256(target_midi)
        total_reference_notes += note_count
        details = stems[source_id]
        active_sources.append(
            {
                "source_id": source_id,
                "program_num": details.get("program_num"),
                "midi_program_name": details.get("midi_program_name"),
                "inst_class": details.get("inst_class"),
                "is_drum": bool(details.get("is_drum")),
                "notes_in_window": note_count,
            }
        )

    if not reference_midis:
        raise ValueError(f"no active MIDI sources in crop for {track_id}")

    return {
        "manifest_entry": {
            "id": track_id,
            "mix": str(target_mix.relative_to(dataset_root)),
            "reference_midis": reference_midis,
            "mix_bytes": target_mix.stat().st_size,
            "reference_midi_count": len(reference_midis),
            "mix_sha256": sha256(target_mix),
            "reference_midi_sha256": cropped_midi_hashes,
        },
        "acquisition": {
            "track_id": track_id,
            "mirror_revision": MIRROR_REVISION,
            "metadata": metadata_download,
            "mix": mix_download,
            "raw_midis": raw_midis,
            "midi_saved_source_count": len(midi_source_ids),
            "active_reference_source_count": len(reference_midis),
            "active_sources": active_sources,
            "segment_start_seconds": SEGMENT_START_SECONDS,
            "segment_duration_seconds": round(duration, 3),
            "reference_notes": total_reference_notes,
        },
    }


def prepare_mr_mt3_checkpoint(mt3_binary: Path, checkpoint_root: Path, output_root: Path) -> dict[str, object]:
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    log_path = output_root / "mr_mt3" / "checkpoint_download.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    process = subprocess.run(
        [str(mt3_binary), "download", "mr_mt3"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=os.environ.copy(),
    )
    elapsed = time.perf_counter() - started
    log_path.write_text(process.stdout or "")
    if process.returncode != 0:
        raise RuntimeError(f"MR-MT3 checkpoint download failed; see {log_path}")
    checkpoint = checkpoint_root / "mr_mt3" / "mt3.pth"
    if not checkpoint.is_file():
        raise RuntimeError(f"MR-MT3 checkpoint missing after download: {checkpoint}")
    actual_hash = sha256(checkpoint)
    if actual_hash != MR_MT3_CHECKPOINT_SHA256:
        raise RuntimeError(
            f"MR-MT3 checkpoint hash mismatch: expected {MR_MT3_CHECKPOINT_SHA256}, got {actual_hash}"
        )
    return {
        "path": str(checkpoint.relative_to(checkpoint_root)),
        "bytes": checkpoint.stat().st_size,
        "sha256": actual_hash,
        "download_seconds": round(elapsed, 3),
    }


def run_mr_mt3_track(mt3_binary: Path, audio_path: Path, output_midi: Path, log_path: Path) -> dict[str, object]:
    output_midi.parent.mkdir(parents=True, exist_ok=True)
    time_path = log_path.with_suffix(".time")
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
        str(output_midi),
        "-m",
        "mr_mt3",
        "--device",
        "cpu",
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
        raise RuntimeError(f"MR-MT3 failed for {audio_path.name}; see {log_path}")
    if not output_midi.is_file():
        raise RuntimeError(f"MR-MT3 produced no MIDI for {audio_path.name}")
    peak_rss_kib = int(time_path.read_text().strip())
    parsed = pretty_midi.PrettyMIDI(str(output_midi))
    return {
        "runtime_seconds": round(elapsed, 3),
        "process_max_rss_mb": round(peak_rss_kib / 1024.0, 2),
        "predicted_notes": sum(len(instrument.notes) for instrument in parsed.instruments),
        "predicted_streams": [
            {
                "program": int(instrument.program),
                "is_drum": bool(instrument.is_drum),
                "notes": len(instrument.notes),
            }
            for instrument in parsed.instruments
        ],
    }


def main() -> None:
    output_root = Path(os.environ.get("MULTITRACK_SMOKE_OUTPUT", "smoke-output")).resolve()
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
    if not mt3_binary.is_file():
        raise RuntimeError(f"MT3 runner executable missing: {mt3_binary}")
    checkpoint_root = Path(os.environ["MT3_CHECKPOINT_DIR"]).resolve()
    checkpoint = prepare_mr_mt3_checkpoint(mt3_binary, checkpoint_root, output_root)

    mt3_root = output_root / "mr_mt3"
    mt3_entries: list[dict[str, object]] = []
    for track_id in TRACK_IDS:
        audio_path = dataset_root / track_id / "mix.wav"
        predicted_midi = mt3_root / f"{track_id}.mid"
        log_path = mt3_root / f"{track_id}.log"
        operational = run_mr_mt3_track(mt3_binary, audio_path, predicted_midi, log_path)
        mt3_entries.append(
            {
                "id": track_id,
                "predicted_midi": predicted_midi.name,
                **operational,
            }
        )

    mt3_version = os.environ["MT3_INFER_VERSION"]
    mt3_torch_version = os.environ["MT3_TORCH_VERSION"]
    mt3_run = {
        "evaluation_id": "analysis_v3_multitrack_slakh_redux_subset_mr_mt3",
        "hello_ai_sha": hello_ai_sha,
        "candidate": "mr_mt3_via_mt3_infer",
        "candidate_revision": (
            f"mt3-infer=={mt3_version}@{MT3_INFER_SOURCE_REVISION}; backend=mr_mt3"
        ),
        "model_checksum": checkpoint["sha256"],
        "dataset_manifest": {"path": str(manifest_path), "sha256": manifest_hash},
        "code_license": "MIT (mt3-infer; MR-MT3 vendored code per runner LICENSE)",
        "weight_license": "MIT per gudgud1014/MR-MT3 model repository metadata",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "device": "cpu",
            "mt3_infer": mt3_version,
            "mt3_runner_torch": mt3_torch_version,
            "mt3_runner_executable": str(mt3_binary),
        },
        "runner_source_revision": MT3_INFER_SOURCE_REVISION,
        "checkpoint_files": [checkpoint],
        "entries": mt3_entries,
    }
    mt3_run_path = mt3_root / "model_run.json"
    mt3_run_path.write_text(json.dumps(mt3_run, indent=2) + "\n")
    mt3_score = score_model_run(manifest_path, mt3_run_path, dataset_root=dataset_root)
    (mt3_root / "score.json").write_text(json.dumps(mt3_score, indent=2) + "\n")

    summary = {
        "scope": "small_decisive_protocol_subset",
        "adoption_eligible": False,
        "reason": "Five 30-second test excerpts are sufficient for a real per-source signal, not a final adoption decision.",
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
            "checkpoint": checkpoint,
            "runtime_seconds_by_track": {
                entry["id"]: entry["runtime_seconds"] for entry in mt3_entries
            },
            "peak_rss_mb_by_track": {
                entry["id"]: entry["process_max_rss_mb"] for entry in mt3_entries
            },
            "predicted_streams_by_track": {
                entry["id"]: entry["predicted_streams"] for entry in mt3_entries
            },
        },
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

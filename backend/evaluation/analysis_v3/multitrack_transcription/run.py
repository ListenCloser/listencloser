"""Analysis V3 generic multi-instrument transcription evaluation runner.

Required CI never downloads datasets or model checkpoints. Dataset extraction,
model inference, and scoring are explicit opt-in commands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

from .datasets.slakh import build_slakh_manifest, write_manifest
from .metrics import NoteEvent, score_events

ROOT = Path(__file__).parent


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_midi_events(paths: list[Path]) -> list[NoteEvent]:
    import pretty_midi

    events: list[NoteEvent] = []
    for path in paths:
        midi = pretty_midi.PrettyMIDI(str(path))
        for instrument in midi.instruments:
            for note in instrument.notes:
                events.append(
                    NoteEvent(
                        pitch=int(note.pitch),
                        start=float(note.start),
                        end=float(note.end),
                        program=int(instrument.program),
                        is_drum=bool(instrument.is_drum),
                    )
                )
    return events


def _validate_model_run(payload: dict[str, Any]) -> None:
    required_strings = (
        "evaluation_id",
        "hello_ai_sha",
        "candidate",
        "candidate_revision",
        "code_license",
        "weight_license",
    )
    for key in required_strings:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"model run requires non-empty {key}")
    if "model_checksum" not in payload:
        raise ValueError("model run requires model_checksum key (null only if unavailable)")
    checksum = payload["model_checksum"]
    if checksum is not None and (not isinstance(checksum, str) or not checksum.strip()):
        raise ValueError("model_checksum must be a non-empty string or null")
    manifest_ref = payload.get("dataset_manifest")
    if not isinstance(manifest_ref, dict) or not manifest_ref:
        raise ValueError("model run requires dataset_manifest provenance")
    manifest_sha = manifest_ref.get("sha256")
    if not isinstance(manifest_sha, str) or len(manifest_sha) != 64:
        raise ValueError("dataset_manifest requires a sha256 checksum")
    if not isinstance(payload.get("environment"), dict) or not payload["environment"]:
        raise ValueError("model run requires non-empty environment metadata")
    if not isinstance(payload.get("entries"), list) or not payload["entries"]:
        raise ValueError("model run requires at least one prediction entry")
    seen: set[str] = set()
    for entry in payload["entries"]:
        track_id = entry.get("id")
        predicted_midi = entry.get("predicted_midi")
        if not isinstance(track_id, str) or not track_id:
            raise ValueError("every prediction entry requires non-empty id")
        if track_id in seen:
            raise ValueError(f"duplicate model-run track id: {track_id}")
        seen.add(track_id)
        if not isinstance(predicted_midi, str) or not predicted_midi:
            raise ValueError(f"prediction {track_id} requires predicted_midi")


def _manifest_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("dataset manifest requires non-empty entries")
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        track_id = entry.get("id")
        if not isinstance(track_id, str) or not track_id:
            raise ValueError("dataset entries require non-empty id")
        if track_id in by_id:
            raise ValueError(f"duplicate dataset track id: {track_id}")
        by_id[track_id] = entry
    return by_id


def score_model_run(
    manifest_path: Path,
    model_run_path: Path,
    *,
    dataset_root: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    model_run = json.loads(model_run_path.read_text())
    _validate_model_run(model_run)
    expected_manifest_sha = model_run["dataset_manifest"]["sha256"]
    actual_manifest_sha = _file_sha256(manifest_path)
    if expected_manifest_sha != actual_manifest_sha:
        raise ValueError("model run dataset_manifest checksum does not match manifest")
    dataset_entries = _manifest_entries(manifest)

    prediction_ids = {entry["id"] for entry in model_run["entries"]}
    unknown = sorted(prediction_ids - set(dataset_entries))
    if unknown:
        raise ValueError(f"model run contains ids absent from dataset manifest: {unknown}")

    scored: list[dict[str, Any]] = []
    for prediction in model_run["entries"]:
        track_id = prediction["id"]
        dataset_entry = dataset_entries[track_id]
        reference_paths = [dataset_root / relative for relative in dataset_entry["reference_midis"]]
        predicted_path = model_run_path.parent / prediction["predicted_midi"]
        if not predicted_path.is_file():
            raise ValueError(f"missing predicted MIDI for {track_id}: {predicted_path}")
        missing_reference = [str(path) for path in reference_paths if not path.is_file()]
        if missing_reference:
            raise ValueError(f"missing reference MIDI for {track_id}: {missing_reference}")

        reference = _load_midi_events(reference_paths)
        predicted = _load_midi_events([predicted_path])
        scored.append(
            {
                "id": track_id,
                "reference_source_count": len(reference_paths),
                "metrics": score_events(reference, predicted),
                "runtime_seconds": prediction.get("runtime_seconds"),
                "process_max_rss_mb": prediction.get("process_max_rss_mb"),
            }
        )

    metric_names = list(scored[0]["metrics"])
    macro_f1 = {
        metric: round(
            sum(float(entry["metrics"][metric]["f1"]) for entry in scored) / len(scored),
            4,
        )
        for metric in metric_names
    }
    return {
        "evaluation_id": model_run["evaluation_id"],
        "candidate": model_run["candidate"],
        "candidate_revision": model_run["candidate_revision"],
        "dataset": manifest.get("name"),
        "split": manifest.get("split"),
        "tracks_scored": len(scored),
        "macro_f1": macro_f1,
        "entries": scored,
        "provenance": {
            "hello_ai_sha": model_run["hello_ai_sha"],
            "code_license": model_run["code_license"],
            "weight_license": model_run["weight_license"],
            "model_checksum": model_run.get("model_checksum"),
            "dataset_manifest": model_run["dataset_manifest"],
            "environment": model_run["environment"],
        },
    }


def run_basic_pitch_baseline(
    manifest_path: Path,
    *,
    dataset_root: Path,
    output_dir: Path,
    hello_ai_sha: str,
    limit: int | None = None,
) -> dict[str, Any]:
    from .adapters.basic_pitch import run_basic_pitch

    manifest = json.loads(manifest_path.read_text())
    entries = manifest.get("entries", [])
    if limit is not None:
        entries = entries[:limit]
    if not entries:
        raise ValueError("dataset manifest has no entries to run")

    output_dir.mkdir(parents=True, exist_ok=True)
    predictions = []
    provenance: dict[str, Any] | None = None
    for entry in entries:
        track_id = entry["id"]
        audio_path = dataset_root / entry["mix"]
        if not audio_path.is_file():
            raise ValueError(f"missing audio for {track_id}: {audio_path}")
        midi_name = f"{track_id}.mid"
        measurement = run_basic_pitch(audio_path, output_dir / midi_name)
        provenance = measurement["provenance"]
        predictions.append(
            {
                "id": track_id,
                "predicted_midi": midi_name,
                "runtime_seconds": measurement["runtime_seconds"],
                "process_max_rss_mb": measurement["process_max_rss_mb"],
                "predicted_notes": measurement["predicted_notes"],
                "program_attribution": measurement["program_attribution"],
                "drum_attribution": measurement["drum_attribution"],
            }
        )

    return {
        "evaluation_id": "analysis_v3_multitrack_basic_pitch",
        "hello_ai_sha": hello_ai_sha,
        "candidate": "hello_ai_basic_pitch",
        "candidate_revision": (
            provenance.get("library_version", "unknown") if provenance else "unknown"
        ),
        "model_checksum": None,
        "dataset_manifest": {
            "path": str(manifest_path),
            "sha256": _file_sha256(manifest_path),
        },
        "code_license": "Apache-2.0",
        "weight_license": "Apache-2.0 per upstream package/model repository metadata",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "device": "cpu",
        },
        "engine_provenance": provenance,
        "entries": predictions,
    }


def load_reference_evidence(path: Path | None = None) -> dict[str, Any]:
    path = path or ROOT / "results" / "reference_evidence.json"
    payload = json.loads(path.read_text())
    registry = payload.get("source_registry")
    if not isinstance(registry, dict) or not registry:
        raise ValueError("reference evidence requires source_registry")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("reference evidence requires candidates")
    for candidate in candidates:
        refs = candidate.get("source_refs")
        if not isinstance(refs, list) or not refs:
            raise ValueError("every candidate requires source_refs")
        unknown = sorted(set(refs) - set(registry))
        if unknown:
            raise ValueError(f"unknown source refs: {unknown}")
        if candidate.get("decision") not in {"ADOPT", "RESEARCH", "REJECT", "REVISIT"}:
            raise ValueError("candidate decision must use canonical decision vocabulary")

    traced = [*payload.get("excluded_references", [])]
    dataset = payload.get("dataset")
    if isinstance(dataset, dict):
        traced.append(dataset)
    for entry in traced:
        refs = entry.get("source_refs")
        if not isinstance(refs, list) or not refs:
            raise ValueError("every reference/dataset entry requires source_refs")
        unknown = sorted(set(refs) - set(registry))
        if unknown:
            raise ValueError(f"unknown source refs: {unknown}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Analysis V3 multi-instrument AMT evaluation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("--dataset-root", type=Path, required=True)
    manifest_parser.add_argument("--split", default="test")
    manifest_parser.add_argument("--limit", type=int, default=10)
    manifest_parser.add_argument("--hash-files", action="store_true")
    manifest_parser.add_argument("--output", type=Path, required=True)

    baseline_parser = subparsers.add_parser("basic-pitch")
    baseline_parser.add_argument("--manifest", type=Path, required=True)
    baseline_parser.add_argument("--dataset-root", type=Path, required=True)
    baseline_parser.add_argument("--output-dir", type=Path, required=True)
    baseline_parser.add_argument("--hello-ai-sha", required=True)
    baseline_parser.add_argument("--limit", type=int, default=None)

    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--manifest", type=Path, required=True)
    score_parser.add_argument("--model-run", type=Path, required=True)
    score_parser.add_argument("--dataset-root", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)

    reference_parser = subparsers.add_parser("reference")
    reference_parser.add_argument("--output", type=Path, default=None)

    args = parser.parse_args()
    if args.command == "manifest":
        payload = build_slakh_manifest(
            args.dataset_root,
            split=args.split,
            limit=args.limit,
            hash_files=args.hash_files,
        )
        write_manifest(payload, args.output)
    elif args.command == "basic-pitch":
        payload = run_basic_pitch_baseline(
            args.manifest,
            dataset_root=args.dataset_root,
            output_dir=args.output_dir,
            hello_ai_sha=args.hello_ai_sha,
            limit=args.limit,
        )
        run_path = args.output_dir / "model_run.json"
        run_path.write_text(json.dumps(payload, indent=2) + "\n")
        print(run_path)
    elif args.command == "score":
        payload = score_model_run(
            args.manifest,
            args.model_run,
            dataset_root=args.dataset_root,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n")
        print(args.output)
    else:
        payload = load_reference_evidence()
        if args.output:
            args.output.write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

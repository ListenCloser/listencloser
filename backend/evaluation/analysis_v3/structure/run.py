"""Run music-structure candidates against an explicit annotated manifest."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any

from evaluation.models import CorpusManifest
from evaluation.structure_metrics import compute_structure_boundary_metrics

from .adapters import ADAPTERS, StructureAdapter, StructureMetadata


def _peak_rss_mb() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = raw if sys.platform == "darwin" else raw * 1024.0
    return round(bytes_used / (1024.0 * 1024.0), 2)


def _dataset_key(value: str | None) -> str:
    key = "".join(char for char in (value or "").lower() if char.isalnum())
    if (
        "harmonixset" in key
        or key in {"hx", "bhx"}
        or key.startswith("songformdbhx")
        or key.startswith("songformbenchbhx")
    ):
        return "harmonixset"
    return key


def _same_dataset_family(left: str | None, right: str | None) -> bool:
    left_key = _dataset_key(left)
    right_key = _dataset_key(right)
    if not left_key or not right_key:
        return False
    return left_key == right_key or left_key in right_key or right_key in left_key


def _explicitly_held_out(
    metadata: StructureMetadata,
    dataset: str | None,
    split: str | None,
) -> bool:
    if not any(_same_dataset_family(dataset, item) for item in metadata.held_out_datasets):
        return False
    if metadata.held_out_partition is None:
        return True
    return _dataset_key(split) == _dataset_key(metadata.held_out_partition)


def _has_training_overlap(
    metadata: StructureMetadata,
    dataset: str | None,
    split: str | None,
) -> bool:
    if _explicitly_held_out(metadata, dataset, split):
        return False
    return any(_same_dataset_family(dataset, item) for item in metadata.training_datasets)


def _evaluation_validity(
    metadata: StructureMetadata,
    dataset: str | None,
    split: str | None,
    *,
    overlap: bool,
    allow_training_overlap: bool,
) -> str:
    if overlap:
        return "in_sample_override" if allow_training_overlap else "not_independent"
    if _explicitly_held_out(metadata, dataset, split):
        return "independent_held_out"
    return "no_declared_overlap"


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row.get("metrics")]

    def macro(key: str) -> float | None:
        values = [
            float(row["metrics"][key]) for row in scored if row["metrics"].get(key) is not None
        ]
        return round(mean(values), 4) if values else None

    latencies = [
        float(row["latency_seconds"]) for row in rows if row.get("latency_seconds") is not None
    ]
    return {
        "clips_total": len(rows),
        "clips_scored": len(scored),
        "clips_withheld_training_overlap": sum(
            row.get("status") == "withheld_training_overlap" for row in rows
        ),
        "clips_candidate_error": sum(row.get("status") == "candidate_error" for row in rows),
        "macro_boundary_f1_05": macro("f1_05"),
        "macro_boundary_f1_3": macro("f1_3"),
        "macro_interior_boundary_f1_05": macro("f1_trimmed_05"),
        "macro_interior_boundary_f1_3": macro("f1_trimmed_3"),
        "mean_inference_seconds": round(mean(latencies), 3) if latencies else None,
    }


def run_structure_evaluation(
    candidate: str,
    manifest_path: str,
    *,
    device: str = "cpu",
    allow_training_overlap: bool = False,
    adapter: StructureAdapter | None = None,
) -> dict[str, Any]:
    """Evaluate one candidate without changing production dependencies or routing."""
    manifest = CorpusManifest.from_file(manifest_path)
    if candidate not in ADAPTERS and adapter is None:
        raise ValueError(f"Unknown structure candidate: {candidate}")

    candidate_adapter = adapter or ADAPTERS[candidate](device=device)
    load_start = time.monotonic()
    try:
        candidate_adapter.load()
    except Exception as exc:
        return {
            "task": "structure_boundary_detection",
            "candidate": candidate,
            "manifest": manifest.name,
            "status": "blocked",
            "error": f"{type(exc).__name__}: {exc}",
            "candidate_metadata": asdict(candidate_adapter.metadata()),
        }
    load_seconds = round(time.monotonic() - load_start, 4)
    metadata = candidate_adapter.metadata()

    rows: list[dict[str, Any]] = []
    for clip in manifest.clips:
        row: dict[str, Any] = {
            "clip_id": clip.id,
            "dataset": clip.dataset,
            "split": clip.split,
            "source_id": clip.source_id,
            "license": clip.license,
            "audio_provenance": clip.audio_provenance,
        }
        if not clip.reference.sections:
            row["status"] = "withheld_no_reference_sections"
            rows.append(row)
            continue

        overlap = _has_training_overlap(metadata, clip.dataset, clip.split)
        row["evaluation_validity"] = _evaluation_validity(
            metadata,
            clip.dataset,
            clip.split,
            overlap=overlap,
            allow_training_overlap=allow_training_overlap,
        )
        if overlap and not allow_training_overlap:
            row["status"] = "withheld_training_overlap"
            rows.append(row)
            continue

        audio_path = Path(clip.audio)
        if not audio_path.is_file():
            row["status"] = "blocked_missing_audio"
            row["audio_path"] = str(audio_path)
            rows.append(row)
            continue

        result = candidate_adapter.timed_analyze(str(audio_path))
        row["latency_seconds"] = result.latency_seconds
        row["candidate_output_metadata"] = result.metadata
        if not result.ok:
            row["status"] = "candidate_error"
            row["error"] = result.error
            rows.append(row)
            continue

        metrics = compute_structure_boundary_metrics(result.segments, clip.reference.sections)
        row["status"] = "scored"
        row["predicted_segments"] = result.segments
        row["metrics"] = metrics.to_dict()
        rows.append(row)

    return {
        "task": "structure_boundary_detection",
        "candidate": candidate,
        "manifest": manifest.name,
        "status": "completed",
        "device": device,
        "allow_training_overlap": allow_training_overlap,
        "load_seconds": load_seconds,
        "process_peak_rss_mb": _peak_rss_mb(),
        "candidate_metadata": asdict(metadata),
        "aggregate": _aggregate(rows),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Structure V1 candidate evaluation")
    parser.add_argument("--candidate", required=True, choices=list(ADAPTERS) + ["all"])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda", "mps"])
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent / "results"),
    )
    parser.add_argument(
        "--allow-training-overlap",
        action="store_true",
        help="Run an explicitly labeled in-sample diagnostic instead of withholding overlap",
    )
    args = parser.parse_args()

    candidates = list(ADAPTERS) if args.candidate == "all" else [args.candidate]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_stem = Path(args.manifest).stem

    for candidate in candidates:
        result = run_structure_evaluation(
            candidate,
            args.manifest,
            device=args.device,
            allow_training_overlap=args.allow_training_overlap,
        )
        output_path = output_dir / f"{candidate}_{manifest_stem}.json"
        output_path.write_text(json.dumps(result, indent=2, default=str) + "\n")
        print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()

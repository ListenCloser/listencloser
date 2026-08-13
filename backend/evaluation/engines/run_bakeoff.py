"""CLI runner for OSS engine evaluation bakeoff.

Evaluates candidate OSS engines against the existing corpus without
changing production code paths.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from evaluation.corpus import load_manifest
from evaluation.engines import EngineCategory, run_engine_evaluation, write_evaluation_report

# Import adapter registries
try:
    from evaluation.engines.transcription import (
        get_transcription_adapter,
        list_transcription_adapters,
    )
except ImportError:
    list_transcription_adapters = lambda: []

try:
    from evaluation.engines.beat_tracking import (
        get_beat_tracking_adapter,
        list_beat_tracking_adapters,
    )
except ImportError:
    list_beat_tracking_adapters = lambda: []

try:
    from evaluation.engines.harmony import (
        get_harmony_adapter,
        list_harmony_adapters,
    )
except ImportError:
    list_harmony_adapters = lambda: []

try:
    from evaluation.engines.structure import (
        get_structure_adapter,
        list_structure_adapters,
    )
except ImportError:
    list_structure_adapters = lambda: []


ADAPTER_GETTERS = {
    "transcription": (list_transcription_adapters, get_transcription_adapter),
    "beat_tracking": (list_beat_tracking_adapters, get_beat_tracking_adapter),
    "harmony": (list_harmony_adapters, get_harmony_adapter),
    "structure": (list_structure_adapters, get_structure_adapter),
}


def run_category_evaluation(
    category: EngineCategory,
    manifest_path: str,
    engine_names: list[str],
    output_dir: str,
    device: str = "cpu",
    **adapter_kwargs,
) -> list:
    """Run evaluation for all specified engines in a category."""
    list_fn, get_fn = ADAPTER_GETTERS.get(category, (lambda: [], lambda x: None))
    available = list_fn()

    if not available:
        print(f"No adapters registered for category: {category}")
        return []

    # Filter to requested engines
    if engine_names:
        engines_to_run = [n for n in engine_names if n in available]
        if not engines_to_run:
            print(f"None of the requested engines available for {category}: {available}")
            return []
    else:
        engines_to_run = available

    print(f"Evaluating {category} engines: {engines_to_run}")

    manifest = load_manifest(manifest_path)
    category_clips = manifest.clips

    reports = []
    for engine_name in engines_to_run:
        print(f"\n--- {engine_name} ---")
        try:
            adapter = get_fn(engine_name, device=device, **adapter_kwargs)
            if not adapter.is_available():
                print(f"  SKIP: {engine_name} not available (missing deps or model)")
                continue

            engine_output_dir = os.path.join(output_dir, category, engine_name)
            os.makedirs(engine_output_dir, exist_ok=True)

            report = run_engine_evaluation(
                adapter=adapter,
                clips=category_clips,
                category=category,
                output_dir=engine_output_dir,
                **adapter_kwargs,
            )
            reports.append(report)
            print(f"  Completed: {report.clips_succeeded}/{report.clips_total} clips")
            print(f"  Avg runtime: {report.avg_runtime_s:.2f}s, Memory: {report.avg_peak_memory_mb:.1f}MB")
            print(f"  Aggregate: {report.aggregate_metrics}")

        except Exception as e:
            print(f"  FAILED: {engine_name} - {e}")

    return reports


def main():
    parser = argparse.ArgumentParser(description="OSS Music Engine Evaluation Bakeoff")
    parser.add_argument("--manifest", required=True, help="Path to corpus manifest JSON")
    parser.add_argument("--output", default="evaluation/results/bakeoff", help="Output directory")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda", "mps"], help="Device for GPU engines")
    parser.add_argument("--category", choices=["transcription", "beat_tracking", "harmony", "structure", "all"], default="all")
    parser.add_argument("--engines", nargs="+", help="Specific engine names to evaluate (default: all available)")
    parser.add_argument("--transcription-thresholds", nargs="+", type=float, help="Onset/frame thresholds for Basic Pitch (e.g., 0.5 0.3)")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    categories = [args.category] if args.category != "all" else ["transcription", "beat_tracking", "harmony", "structure"]

    all_reports = []

    for cat in categories:
        cat_reports = run_category_evaluation(
            category=cat,
            manifest_path=args.manifest,
            engine_names=args.engines or [],
            output_dir=args.output,
            device=args.device,
            **(dict(onset_threshold=args.transcription_thresholds[0], frame_threshold=args.transcription_thresholds[1]) if args.transcription_thresholds else {}),
        )
        all_reports.extend(cat_reports)

    # Write comparative report
    report_path = os.path.join(args.output, "bakeoff_report.json")
    write_evaluation_report(all_reports, report_path)
    print(f"\n=== Bakeoff Complete ===")
    print(f"Report: {report_path}")
    print(f"Markdown: {report_path.replace('.json', '.md')}")

    # Print summary table
    print("\n=== SUMMARY ===")
    for r in all_reports:
        status = "OK" if r.clips_succeeded == r.clips_total else "PARTIAL" if r.clips_succeeded > 0 else "FAILED"
        print(f"  {r.engine_name:25s} | {r.category:15s} | {r.clips_succeeded:2d}/{r.clips_total:2d} | {r.avg_runtime_s:5.1f}s | {r.avg_peak_memory_mb:5.1f}MB | {status}")


if __name__ == "__main__":
    main()
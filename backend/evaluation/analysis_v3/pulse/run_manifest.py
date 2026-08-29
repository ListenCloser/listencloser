"""Run pulse candidates against an explicit evaluation manifest.

This complements ``pulse.run`` (which retains the historical diversity probe)
so held-out corpora can be evaluated without renaming or overwriting manifests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters import ADAPTERS
from .run import run_beat_evaluation


def run_manifest(
    candidate: str,
    manifest_path: str,
    *,
    device: str = "cpu",
    allow_training_overlap: bool = False,
) -> dict[str, Any]:
    """Run one candidate against one explicit manifest."""
    return run_beat_evaluation(
        candidate,
        manifest_path,
        device,
        allow_training_overlap=allow_training_overlap,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pulse evaluation on a manifest")
    parser.add_argument(
        "--candidate",
        required=True,
        choices=list(ADAPTERS.keys()) + ["all"],
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "mps"],
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent / "results"),
    )
    parser.add_argument(
        "--allow-training-overlap",
        action="store_true",
        help="Allow an explicitly in-sample probe instead of rejecting overlap",
    )
    args = parser.parse_args()

    candidates = list(ADAPTERS) if args.candidate == "all" else [args.candidate]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_stem = Path(args.manifest).stem

    for candidate in candidates:
        try:
            result = run_manifest(
                candidate,
                args.manifest,
                device=args.device,
                allow_training_overlap=args.allow_training_overlap,
            )
        except Exception as exc:
            result = {
                "candidate": candidate,
                "task": "beat",
                "manifest": args.manifest,
                "error": str(exc),
            }

        output_path = output_dir / f"{candidate}_{manifest_stem}.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()

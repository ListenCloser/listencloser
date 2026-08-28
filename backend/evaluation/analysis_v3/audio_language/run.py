"""Analysis V3 audio-language reference and grounded-output evaluator.

Required-CI-safe usage:
  python -m backend.evaluation.analysis_v3.audio_language.run --task reference
  python -m backend.evaluation.analysis_v3.audio_language.run --task score --assessments PATH

No model checkpoint is imported or downloaded by this runner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .metrics import grounded_value_gate, score_by_condition

ROOT = Path(__file__).parent


def load_reference_evidence(path: Path | None = None) -> dict[str, Any]:
    path = path or ROOT / "results" / "reference_evidence.json"
    with path.open() as handle:
        result = json.load(handle)
    if result.get("local_model_inference_performed") is not False:
        raise ValueError("reference evidence must explicitly record no local model inference")
    return result


def score_assessment_file(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        payload = json.load(handle)
    assessments = payload.get("assessments")
    if not isinstance(assessments, list):
        raise ValueError("assessment file must contain an assessments list")
    grouped = score_by_condition(assessments)
    return {
        "evaluation_id": payload.get("evaluation_id"),
        "hello_ai_sha": payload.get("hello_ai_sha"),
        "model": payload.get("model"),
        "model_version": payload.get("model_version"),
        "model_checksum": payload.get("model_checksum"),
        "annotation_method": payload.get("annotation_method"),
        "by_condition": grouped,
        "grounded_value_gate": grounded_value_gate(grouped),
        "notes": (
            "Scores aggregate claim-level human/manual annotations; they do not infer "
            "factual correctness from fluent model prose."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analysis V3 audio-language evaluation")
    parser.add_argument("--task", choices=["reference", "score"], default="reference")
    parser.add_argument("--assessments", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.task == "reference":
        result = load_reference_evidence()
        default_name = "reference_evidence.json"
    else:
        if args.assessments is None:
            parser.error("--assessments is required for --task score")
        result = score_assessment_file(args.assessments)
        default_name = "scored_assessments.json"

    output = args.output or ROOT / "results" / default_name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print(f"Results saved to {output}")


if __name__ == "__main__":
    main()

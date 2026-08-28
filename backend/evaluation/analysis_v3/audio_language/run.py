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

from .metrics import CONDITIONS, grounded_value_gate, score_by_condition

ROOT = Path(__file__).parent


def load_reference_evidence(path: Path | None = None) -> dict[str, Any]:
    path = path or ROOT / "results" / "reference_evidence.json"
    with path.open() as handle:
        result = json.load(handle)
    if result.get("local_model_inference_performed") is not False:
        raise ValueError("reference evidence must explicitly record no local model inference")
    return result


def _require_nonempty_string(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"assessment file requires non-empty {name}")
    return value


def _validate_scored_run(payload: dict[str, Any], assessments: list[dict[str, Any]]) -> None:
    for name in (
        "evaluation_id",
        "hello_ai_sha",
        "model",
        "model_version",
        "code_license",
        "weight_license",
        "annotation_method",
    ):
        _require_nonempty_string(payload, name)

    if "model_checksum" not in payload:
        raise ValueError("assessment file requires model_checksum key (null only if unobtainable)")
    checksum = payload["model_checksum"]
    if checksum is not None and (not isinstance(checksum, str) or not checksum.strip()):
        raise ValueError("model_checksum must be a non-empty string or null")

    for name in ("environment", "generation", "operational"):
        if not isinstance(payload.get(name), dict) or not payload[name]:
            raise ValueError(f"assessment file requires non-empty {name} object")

    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("assessment file requires non-empty cases list with raw model outputs")

    raw_outputs: set[tuple[str, str, str]] = set()
    seen_case_keys: set[tuple[str, str]] = set()
    required_conditions = set(CONDITIONS)
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each case must be an object")
        case_id = _require_nonempty_string(case, "case_id")
        question_id = _require_nonempty_string(case, "question_id")
        case_key = (case_id, question_id)
        if case_key in seen_case_keys:
            raise ValueError("duplicate case_id/question_id raw cases are not allowed")
        seen_case_keys.add(case_key)

        conditions = case.get("conditions")
        if not isinstance(conditions, dict):
            raise ValueError(f"case {case_id} requires conditions object")
        if set(conditions) != required_conditions:
            raise ValueError(
                f"case {case_id} must contain exactly the three conditions: {CONDITIONS}"
            )
        for condition, output in conditions.items():
            if not isinstance(output, dict):
                raise ValueError(f"case {case_id} condition {condition} must be an object")
            raw_response = output.get("raw_response")
            if not isinstance(raw_response, str) or not raw_response.strip():
                raise ValueError(
                    f"case {case_id} condition {condition} requires non-empty raw_response"
                )
            raw_outputs.add((case_id, question_id, condition))

    assessment_outputs = {
        (
            assessment.get("case_id"),
            assessment.get("question_id"),
            assessment.get("condition"),
        )
        for assessment in assessments
    }
    if assessment_outputs != raw_outputs:
        raise ValueError(
            "assessments must cover every retained case/question/condition raw response exactly"
        )


def score_assessment_file(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        payload = json.load(handle)
    assessments = payload.get("assessments")
    if not isinstance(assessments, list) or not assessments:
        raise ValueError("assessment file must contain a non-empty assessments list")

    _validate_scored_run(payload, assessments)
    grouped = score_by_condition(assessments)
    return {
        "evaluation_id": payload["evaluation_id"],
        "provenance": {
            "hello_ai_sha": payload["hello_ai_sha"],
            "model": payload["model"],
            "model_version": payload["model_version"],
            "model_checksum": payload["model_checksum"],
            "code_license": payload["code_license"],
            "weight_license": payload["weight_license"],
            "environment": payload["environment"],
            "generation": payload["generation"],
            "operational": payload["operational"],
            "annotation_method": payload["annotation_method"],
        },
        "by_condition": grouped,
        "grounded_value_gate": grounded_value_gate(grouped),
        "notes": (
            "Scores aggregate claim-level human/manual annotations tied to retained raw model "
            "outputs; they do not infer factual correctness from fluent model prose."
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

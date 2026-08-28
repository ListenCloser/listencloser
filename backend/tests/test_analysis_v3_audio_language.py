from __future__ import annotations

import json
from pathlib import Path

import pytest
from backend.evaluation.analysis_v3.audio_language.metrics import (
    grounded_value_gate,
    score_assessments,
    score_by_condition,
)
from backend.evaluation.analysis_v3.audio_language.run import (
    load_reference_evidence,
    score_assessment_file,
)


def row(
    condition: str,
    supported: int,
    contradicted: int,
    unsupported: int,
    refs_expected: list[str] | None = None,
    refs_cited: list[str] | None = None,
    should_abstain: bool = False,
    abstained: bool = False,
    usefulness: float | None = 3.0,
    specificity: float | None = 3.0,
    requires_temporal_grounding: bool = False,
    temporal_grounding_correct: bool | None = None,
    case_id: str = "case-1",
    question_id: str = "q",
) -> dict:
    return {
        "case_id": case_id,
        "question_id": question_id,
        "condition": condition,
        "supported_claims": supported,
        "contradicted_claims": contradicted,
        "unsupported_claims": unsupported,
        "total_claims": supported + contradicted + unsupported,
        "expected_support_refs": refs_expected or [],
        "cited_support_refs": refs_cited or [],
        "should_abstain": should_abstain,
        "abstained": abstained,
        "requires_temporal_grounding": requires_temporal_grounding,
        "temporal_grounding_correct": temporal_grounding_correct,
        "usefulness_rating": usefulness,
        "specificity_rating": specificity,
    }


def scored_payload(assessments: list[dict]) -> dict:
    cases: dict[tuple[str, str], dict] = {}
    for assessment in assessments:
        key = (assessment["case_id"], assessment["question_id"])
        case = cases.setdefault(
            key,
            {
                "case_id": assessment["case_id"],
                "question_id": assessment["question_id"],
                "conditions": {},
            },
        )
        case["conditions"][assessment["condition"]] = {
            "raw_response": f"raw response for {assessment['condition']}",
            "latency_seconds": 1.0,
        }
    return {
        "evaluation_id": "eval-1",
        "hello_ai_sha": "abc123",
        "model": "music_flamingo",
        "model_version": "revision-1",
        "model_checksum": "sha256:deadbeef",
        "code_license": "MIT",
        "weight_license": "noncommercial",
        "environment": {"device": "cuda", "hardware": "test-gpu"},
        "generation": {"do_sample": False, "max_new_tokens": 256},
        "operational": {"load_seconds": 1.0, "determinism_repeats": 3},
        "annotation_method": "blinded manual annotation",
        "cases": list(cases.values()),
        "assessments": assessments,
    }


def complete_assessments() -> list[dict]:
    return [
        row("audio_only", 1, 0, 1, usefulness=2, specificity=3),
        row("evidence_only", 1, 0, 1, usefulness=3, specificity=3),
        row("audio_plus_evidence", 2, 0, 0, usefulness=4, specificity=4),
    ]


def test_score_assessments_known_rates() -> None:
    result = score_assessments(
        [
            row("audio_only", 2, 1, 0, ["a", "b"], ["a", "x"], usefulness=4),
            row(
                "audio_only",
                2,
                0,
                1,
                ["c"],
                ["c"],
                usefulness=2,
                case_id="case-2",
            ),
        ]
    )
    assert result["supported_claim_rate"] == pytest.approx(4 / 6)
    assert result["contradiction_rate"] == pytest.approx(1 / 6, abs=1e-6)
    assert result["unsupported_claim_rate"] == pytest.approx(1 / 6, abs=1e-6)
    assert result["citation_recall"] == pytest.approx(2 / 3, abs=1e-6)
    assert result["citation_precision"] == pytest.approx(2 / 3, abs=1e-6)
    assert result["abstention_accuracy"] == 1.0
    assert result["mean_usefulness_rating"] == 3.0


def test_grounded_value_gate_passes_only_on_bounded_improvement() -> None:
    grouped = score_by_condition(
        [
            row(
                "evidence_only",
                3,
                1,
                1,
                ["a"],
                ["a"],
                usefulness=3,
                specificity=4,
            ),
            row(
                "audio_plus_evidence",
                5,
                0,
                0,
                ["a"],
                ["a"],
                usefulness=4,
                specificity=4,
            ),
        ]
    )
    assert grounded_value_gate(grouped)["passes"] is True

    worse = score_by_condition(
        [
            row("evidence_only", 3, 0, 1, usefulness=3, specificity=4),
            row("audio_plus_evidence", 4, 0, 2, usefulness=4, specificity=4),
        ]
    )
    result = grounded_value_gate(worse)
    assert result["passes"] is False
    assert result["criteria"]["unsupported_claim_rate_not_worse"] is False


def test_grounded_value_gate_rejects_mismatched_coverage() -> None:
    grouped = score_by_condition(
        [
            row("evidence_only", 1, 0, 1, case_id="case-a"),
            row("audio_plus_evidence", 2, 0, 0, case_id="case-b", usefulness=4),
        ]
    )
    result = grounded_value_gate(grouped)
    assert result["evaluable"] is False
    assert "same case_id/question_id coverage" in result["reason"]


def test_duplicate_assessment_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        score_assessments(
            [
                row("audio_only", 1, 0, 0),
                row("audio_only", 1, 0, 0),
            ]
        )


def test_grounded_value_gate_requires_human_ratings() -> None:
    grouped = score_by_condition(
        [
            row("evidence_only", 1, 0, 0, usefulness=None, specificity=None),
            row("audio_plus_evidence", 2, 0, 0, usefulness=None, specificity=None),
        ]
    )
    assert grounded_value_gate(grouped)["evaluable"] is False


def test_score_by_condition_keeps_conditions_separate() -> None:
    result = score_by_condition(
        [row("audio_only", 1, 0, 0), row("evidence_only", 0, 0, 1)]
    )
    assert result["audio_only"]["supported_claim_rate"] == 1.0
    assert result["evidence_only"]["unsupported_claim_rate"] == 1.0


def test_invalid_claim_sum_is_rejected() -> None:
    item = row("audio_only", 1, 0, 0)
    item["total_claims"] = 2
    with pytest.raises(ValueError, match="sum"):
        score_assessments([item])


def test_invalid_condition_is_rejected() -> None:
    with pytest.raises(ValueError, match="condition"):
        score_assessments([row("unknown", 1, 0, 0)])


def test_invalid_rating_is_rejected() -> None:
    with pytest.raises(ValueError, match="usefulness_rating"):
        score_assessments([row("audio_only", 1, 0, 0, usefulness=6)])


def test_missing_case_id_is_rejected() -> None:
    item = row("audio_only", 1, 0, 0)
    item["case_id"] = ""
    with pytest.raises(ValueError, match="case_id"):
        score_assessments([item])


def test_zero_claim_abstention_item_is_valid() -> None:
    result = score_assessments(
        [
            row(
                "evidence_only",
                0,
                0,
                0,
                should_abstain=True,
                abstained=True,
                usefulness=3,
                specificity=3,
            )
        ]
    )
    assert result["supported_claim_rate"] is None
    assert result["abstention_accuracy"] == 1.0


def test_temporal_grounding_accuracy_and_gate() -> None:
    grouped = score_by_condition(
        [
            row(
                "evidence_only",
                2,
                0,
                0,
                usefulness=3,
                specificity=4,
                requires_temporal_grounding=True,
                temporal_grounding_correct=True,
            ),
            row(
                "audio_plus_evidence",
                3,
                0,
                0,
                usefulness=4,
                specificity=4,
                requires_temporal_grounding=True,
                temporal_grounding_correct=False,
            ),
        ]
    )
    assert grouped["evidence_only"]["temporal_grounding_accuracy"] == 1.0
    result = grounded_value_gate(grouped)
    assert result["passes"] is False
    assert result["criteria"]["temporal_grounding_not_worse"] is False


def test_required_temporal_grounding_requires_annotation() -> None:
    with pytest.raises(ValueError, match="temporal_grounding_correct"):
        score_assessments(
            [
                row(
                    "audio_only",
                    1,
                    0,
                    0,
                    requires_temporal_grounding=True,
                    temporal_grounding_correct=None,
                )
            ]
        )


def test_load_reference_evidence_rejects_local_inference_flag(tmp_path: Path) -> None:
    path = tmp_path / "reference.json"
    path.write_text(json.dumps({"local_model_inference_performed": True}))
    with pytest.raises(ValueError, match="no local model inference"):
        load_reference_evidence(path)


def test_score_assessment_file_preserves_required_provenance(tmp_path: Path) -> None:
    path = tmp_path / "assessments.json"
    path.write_text(json.dumps(scored_payload(complete_assessments())))

    result = score_assessment_file(path)

    assert result["provenance"]["hello_ai_sha"] == "abc123"
    assert result["provenance"]["model_version"] == "revision-1"
    assert result["provenance"]["model_checksum"] == "sha256:deadbeef"
    assert result["provenance"]["environment"]["hardware"] == "test-gpu"
    assert set(result["by_condition"]) == {
        "audio_only",
        "evidence_only",
        "audio_plus_evidence",
    }
    assert result["grounded_value_gate"]["passes"] is True


def test_score_assessment_file_rejects_missing_provenance(tmp_path: Path) -> None:
    payload = scored_payload(complete_assessments())
    del payload["model_version"]
    path = tmp_path / "assessments.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="model_version"):
        score_assessment_file(path)


def test_score_assessment_file_requires_all_three_conditions(tmp_path: Path) -> None:
    payload = scored_payload(complete_assessments())
    del payload["cases"][0]["conditions"]["audio_only"]
    path = tmp_path / "assessments.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="three conditions"):
        score_assessment_file(path)


def test_score_assessment_file_requires_matching_raw_response(tmp_path: Path) -> None:
    payload = scored_payload(complete_assessments())
    payload["cases"][0]["conditions"]["audio_only"]["raw_response"] = ""
    path = tmp_path / "assessments.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="raw_response"):
        score_assessment_file(path)


def test_score_assessment_file_rejects_duplicate_raw_cases(tmp_path: Path) -> None:
    payload = scored_payload(complete_assessments())
    payload["cases"].append(dict(payload["cases"][0]))
    path = tmp_path / "assessments.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="duplicate case_id/question_id raw cases"):
        score_assessment_file(path)

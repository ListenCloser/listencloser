import json

import pytest

from domain.capability_policy import load_capability_registry
from evaluation.analysis_v3 import claim_sufficiency
from evaluation.analysis_v3.claim_sufficiency import (
    claims_by_readiness,
    load_claim_sufficiency_contract,
)


def _claims_by_id():
    payload = load_claim_sufficiency_contract()
    return {claim["claim_id"]: claim for claim in payload["claims"]}


def _write_contract(tmp_path, claim):
    path = tmp_path / "claim_sufficiency.json"
    path.write_text(json.dumps({"schema_version": 1, "claims": [claim]}), encoding="utf-8")
    return path


def _minimal_claim(**overrides):
    claim = {
        "claim_id": "test_claim",
        "claim_text": "The piece is in a global key.",
        "readiness": "SUPPORTED_NOW",
        "required_capabilities": ["key"],
        "optional_capabilities": [],
        "planned_evidence": [],
        "temporal_granularity": "whole_work",
        "quality_gates": ["AGGREGATE_ONLY"],
        "validated_domains": ["global_key_benchmark_domain"],
        "abstention_rule": "Withhold when evidence is absent.",
        "proof_actions": ["show_evidence"],
        "framework": None,
    }
    claim.update(overrides)
    return claim


def test_claim_sufficiency_contract_loads_representative_gates():
    claims = _claims_by_id()
    assert len(claims) >= 10
    assert {
        "global_key_identification",
        "localized_chord_label",
        "named_section_density_contrast",
        "melody_transposed_return",
        "groove_anticipates_downbeat",
        "tonal_motion_toward_dominant",
        "multidimensional_drop_change",
    } <= set(claims)


def test_supported_now_claims_depend_only_on_production_capabilities_and_name_domains():
    registry = load_capability_registry()
    supported = claims_by_readiness("SUPPORTED_NOW")
    assert supported
    for claim in supported:
        assert claim["required_capabilities"]
        assert claim["planned_evidence"] == []
        assert claim["validated_domains"]
        for capability in claim["required_capabilities"]:
            assert registry[capability]["status"] == "production"


def test_current_withheld_or_evaluation_only_evidence_fails_closed():
    claims = _claims_by_id()
    assert claims["named_section_density_contrast"]["readiness"] != "SUPPORTED_NOW"
    assert claims["melody_transposed_return"]["readiness"] != "SUPPORTED_NOW"
    assert claims["local_modulation"]["readiness"] != "SUPPORTED_NOW"
    assert claims["cadential_resolution"]["readiness"] != "SUPPORTED_NOW"


def test_global_tempo_does_not_unlock_downbeat_relative_groove_claims():
    claim = _claims_by_id()["groove_anticipates_downbeat"]
    assert claim["readiness"] == "BLOCKED_BY_MISSING_EVIDENCE"
    assert "tempo" in claim["required_capabilities"]
    assert "trusted_metric_grid_with_downbeat_phase" in claim["planned_evidence"]
    assert "localized_source_or_onset_events" in claim["planned_evidence"]
    assert "EXACT_EVENT_REQUIRED" in claim["quality_gates"]
    assert "EVENT_COVERAGE_REQUIRED" in claim["quality_gates"]
    assert "coverage" in claim["abstention_rule"]


def test_framework_specific_claims_declare_framework_and_abstention():
    for claim in load_claim_sufficiency_contract()["claims"]:
        if "STYLE_CONTEXT_REQUIRED" not in claim["quality_gates"]:
            continue
        assert claim["framework"]
        assert claim["abstention_rule"]


def test_user_selected_spans_can_unlock_density_without_trusted_sections():
    claims = _claims_by_id()
    selected = claims["user_selected_rhythm_density_contrast"]
    named = claims["named_section_density_contrast"]
    assert selected["readiness"] == "SUPPORTED_NOW"
    assert "USER_SELECTION_CAN_SUBSTITUTE_STRUCTURE" in selected["quality_gates"]
    assert named["readiness"] == "BLOCKED_BY_EVIDENCE_QUALITY"
    assert "section" in named["required_capabilities"]


def test_multidimensional_change_requires_corroborating_evidence():
    claim = _claims_by_id()["multidimensional_drop_change"]
    assert claim["readiness"] == "BLOCKED_BY_MISSING_EVIDENCE"
    assert "MULTI_EVIDENCE_CORROBORATION" in claim["quality_gates"]
    assert len(claim["planned_evidence"]) >= 3


def test_supported_claim_must_require_at_least_one_capability(monkeypatch, tmp_path):
    path = _write_contract(tmp_path, _minimal_claim(required_capabilities=[]))
    monkeypatch.setattr(claim_sufficiency, "_CONTRACT_PATH", path)

    with pytest.raises(ValueError, match="must require at least one capability"):
        load_claim_sufficiency_contract()


def test_supported_claim_cannot_smuggle_withheld_capability(monkeypatch, tmp_path):
    path = _write_contract(tmp_path, _minimal_claim(required_capabilities=["cadence"]))
    monkeypatch.setattr(claim_sufficiency, "_CONTRACT_PATH", path)

    with pytest.raises(ValueError, match="non-production capabilities"):
        load_claim_sufficiency_contract()


def test_supported_claim_must_declare_validated_domain(monkeypatch, tmp_path):
    path = _write_contract(tmp_path, _minimal_claim(validated_domains=[]))
    monkeypatch.setattr(claim_sufficiency, "_CONTRACT_PATH", path)

    with pytest.raises(ValueError, match="must declare a validated domain"):
        load_claim_sufficiency_contract()


def test_claim_metadata_rejects_blank_proof_action(monkeypatch, tmp_path):
    path = _write_contract(tmp_path, _minimal_claim(proof_actions=[" "]))
    monkeypatch.setattr(claim_sufficiency, "_CONTRACT_PATH", path)

    with pytest.raises(ValueError, match="proof_actions must be a list of non-empty strings"):
        load_claim_sufficiency_contract()


def test_missing_evidence_blocker_must_name_missing_evidence(monkeypatch, tmp_path):
    path = _write_contract(
        tmp_path,
        _minimal_claim(readiness="BLOCKED_BY_MISSING_EVIDENCE", planned_evidence=[]),
    )
    monkeypatch.setattr(claim_sufficiency, "_CONTRACT_PATH", path)

    with pytest.raises(ValueError, match="must name planned evidence"):
        load_claim_sufficiency_contract()

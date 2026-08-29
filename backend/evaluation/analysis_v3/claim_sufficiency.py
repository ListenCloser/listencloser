"""Validation helpers for Analysis V3 claim-sufficiency research contracts.

This module is evaluation/architecture-only. It does not route production analysis
or make product claims visible. The checked-in contract connects user-facing claim
classes to the evidence required before those claims are safe.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain.capability_policy import load_capability_registry

_CONTRACT_PATH = Path(__file__).with_name("claim_sufficiency.json")
_ALLOWED_READINESS = {
    "SUPPORTED_NOW",
    "BLOCKED_BY_EVIDENCE_QUALITY",
    "BLOCKED_BY_MISSING_EVIDENCE",
    "STYLE_SPECIFIC_RESEARCH",
    "SEMANTIC_ONLY",
}
_ALLOWED_GATES = {
    "EXACT_EVENT_REQUIRED",
    "EVENT_COVERAGE_REQUIRED",
    "LOCALIZATION_TOLERANT",
    "AGGREGATE_ONLY",
    "MULTI_EVIDENCE_CORROBORATION",
    "STYLE_CONTEXT_REQUIRED",
    "USER_SELECTION_CAN_SUBSTITUTE_STRUCTURE",
    "SEMANTIC_HYPOTHESIS_ONLY",
}


def _require_nonempty_strings(claim_id: str, field: str, value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"claim {claim_id!r} {field} must be a list of non-empty strings")
    return value


def load_claim_sufficiency_contract() -> dict[str, Any]:
    """Load and validate the checked-in claim-sufficiency research contract."""

    payload = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported claim sufficiency schema_version")

    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("claim sufficiency contract must contain claims")

    capability_registry = load_capability_registry()
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("claim entries must be objects")
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise ValueError("every claim must define claim_id")
        if claim_id in seen:
            raise ValueError(f"duplicate claim_id: {claim_id}")
        seen.add(claim_id)

        claim_text = claim.get("claim_text")
        if not isinstance(claim_text, str) or not claim_text.strip():
            raise ValueError(f"claim {claim_id!r} must define claim_text")
        temporal_granularity = claim.get("temporal_granularity")
        if not isinstance(temporal_granularity, str) or not temporal_granularity.strip():
            raise ValueError(f"claim {claim_id!r} must define temporal_granularity")

        readiness = claim.get("readiness")
        if readiness not in _ALLOWED_READINESS:
            raise ValueError(f"claim {claim_id!r} has invalid readiness {readiness!r}")

        gates = _require_nonempty_strings(claim_id, "quality_gates", claim.get("quality_gates"))
        if not gates:
            raise ValueError(f"claim {claim_id!r} must define quality_gates")
        unknown_gates = set(gates) - _ALLOWED_GATES
        if unknown_gates:
            raise ValueError(f"claim {claim_id!r} has unknown quality gates: {sorted(unknown_gates)}")

        required = _require_nonempty_strings(
            claim_id, "required_capabilities", claim.get("required_capabilities", [])
        )
        optional = _require_nonempty_strings(
            claim_id, "optional_capabilities", claim.get("optional_capabilities", [])
        )
        unknown_capabilities = (set(required) | set(optional)) - set(capability_registry)
        if unknown_capabilities:
            raise ValueError(
                f"claim {claim_id!r} references unregistered capabilities: {sorted(unknown_capabilities)}"
            )

        planned = _require_nonempty_strings(claim_id, "planned_evidence", claim.get("planned_evidence", []))
        proof_actions = _require_nonempty_strings(claim_id, "proof_actions", claim.get("proof_actions"))
        if not proof_actions:
            raise ValueError(f"claim {claim_id!r} must define proof_actions")

        abstention_rule = claim.get("abstention_rule")
        if not isinstance(abstention_rule, str) or not abstention_rule.strip():
            raise ValueError(f"claim {claim_id!r} must define an abstention_rule")
        validated_domains = _require_nonempty_strings(
            claim_id, "validated_domains", claim.get("validated_domains")
        )

        if "STYLE_CONTEXT_REQUIRED" in gates and not claim.get("framework"):
            raise ValueError(f"claim {claim_id!r} requires an explicit framework")
        if readiness == "STYLE_SPECIFIC_RESEARCH" and "STYLE_CONTEXT_REQUIRED" not in gates:
            raise ValueError(f"style-specific claim {claim_id!r} must require style context")
        if readiness == "SEMANTIC_ONLY" and "SEMANTIC_HYPOTHESIS_ONLY" not in gates:
            raise ValueError(f"semantic-only claim {claim_id!r} must use the semantic hypothesis gate")
        if readiness == "BLOCKED_BY_MISSING_EVIDENCE" and not planned:
            raise ValueError(f"missing-evidence claim {claim_id!r} must name planned evidence")

        non_production = [
            capability
            for capability in required
            if capability_registry[capability]["status"] != "production"
        ]
        if readiness == "SUPPORTED_NOW":
            if not required:
                raise ValueError(f"supported claim {claim_id!r} must require at least one capability")
            if planned:
                raise ValueError(f"supported claim {claim_id!r} cannot depend on planned evidence")
            if non_production:
                raise ValueError(
                    f"supported claim {claim_id!r} depends on non-production capabilities: {non_production}"
                )
            if not validated_domains:
                raise ValueError(f"supported claim {claim_id!r} must declare a validated domain")
        if readiness == "BLOCKED_BY_EVIDENCE_QUALITY" and not non_production:
            raise ValueError(
                f"evidence-quality-blocked claim {claim_id!r} must identify a non-production required capability"
            )

    return payload


def claims_by_readiness(readiness: str) -> list[dict[str, Any]]:
    """Return research claim gates with one readiness classification."""

    if readiness not in _ALLOWED_READINESS:
        raise ValueError(f"unknown readiness: {readiness}")
    return [
        claim
        for claim in load_claim_sufficiency_contract()["claims"]
        if claim["readiness"] == readiness
    ]

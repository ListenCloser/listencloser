"""Machine-readable product capability maturity and exposure policy.

The registry is the backend source of truth for whether an analysis capability is
production-visible, available to Ask, or intentionally withheld. Algorithm
implementations should not infer product maturity from whether code exists.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

CapabilityStatus = Literal["production", "experimental", "evaluation_only", "withheld"]
_ALLOWED_STATUSES: set[str] = {"production", "experimental", "evaluation_only", "withheld"}
_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "capabilities.json"


class ExposurePolicy(TypedDict):
    inspector: bool
    annotations: bool
    ask: bool


class CapabilityPolicy(TypedDict, total=False):
    status: CapabilityStatus
    input: str
    engine: str
    requires: list[str]
    exposure: ExposurePolicy
    evaluation: dict[str, Any]
    reason: str
    notes: str


@lru_cache(maxsize=1)
def load_capability_registry() -> dict[str, CapabilityPolicy]:
    """Load and validate the checked-in capability policy registry."""
    payload = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported capability registry schema_version")

    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        raise ValueError("capability registry must contain capabilities")

    for name, policy in capabilities.items():
        if not isinstance(policy, dict):
            raise ValueError(f"capability {name!r} must be an object")
        status = policy.get("status")
        if status not in _ALLOWED_STATUSES:
            raise ValueError(f"capability {name!r} has invalid status {status!r}")
        exposure = policy.get("exposure")
        if not isinstance(exposure, dict):
            raise ValueError(f"capability {name!r} must define exposure")
        for surface in ("inspector", "annotations", "ask"):
            if not isinstance(exposure.get(surface), bool):
                raise ValueError(f"capability {name!r} exposure.{surface} must be boolean")
        if status == "withheld":
            if any(exposure.values()):
                raise ValueError(f"withheld capability {name!r} cannot be product-exposed")
            if not policy.get("reason"):
                raise ValueError(f"withheld capability {name!r} must document a reason")

    return capabilities


def capability_policy(kind: str) -> CapabilityPolicy:
    """Return the policy for a registered insight/capability kind."""
    try:
        return load_capability_registry()[kind]
    except KeyError as exc:
        raise KeyError(f"unregistered capability: {kind}") from exc


def is_exposed(kind: str, surface: Literal["inspector", "annotations", "ask"]) -> bool:
    """Return whether a registered capability may appear on a product surface."""
    return capability_policy(kind)["exposure"][surface]


def is_product_evidence(kind: str) -> bool:
    """Return whether normal product evidence may be persisted/exposed.

    Experimental capabilities may still be surfaced when their explicit exposure policy
    allows it; evaluation-only and withheld capabilities are never normal product evidence.
    """
    return capability_policy(kind)["status"] in {"production", "experimental"}


def required_evidence(kind: str) -> tuple[str, ...]:
    """Return named upstream trust requirements for a derived capability."""
    return tuple(capability_policy(kind).get("requires", []))

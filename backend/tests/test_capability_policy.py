from domain.capability_policy import (
    capability_policy,
    is_exposed,
    is_product_evidence,
    load_capability_registry,
    required_evidence,
)


def test_registry_loads_and_has_expected_core_capabilities():
    registry = load_capability_registry()
    assert {
        "key",
        "chord",
        "roman_numeral",
        "harmonic_function",
        "cadence",
        "key_region",
    } <= set(registry)


def test_withheld_capabilities_cannot_leak_to_product_surfaces():
    for kind in ("cadence", "key_region", "harmonic_rhythm", "voice_leading"):
        assert capability_policy(kind)["status"] == "withheld"
        assert not is_product_evidence(kind)
        assert not is_exposed(kind, "inspector")
        assert not is_exposed(kind, "annotations")
        assert not is_exposed(kind, "ask")


def test_withheld_capabilities_must_document_reason():
    for kind in ("cadence", "key_region", "harmonic_rhythm", "voice_leading"):
        policy = capability_policy(kind)
        assert policy.get("reason"), f"{kind} must document a reason for being withheld"


def test_theory_claims_require_trusted_chord_and_key():
    assert required_evidence("roman_numeral") == ("trusted_chord", "trusted_key")
    assert required_evidence("harmonic_function") == ("trusted_chord", "trusted_key")


def test_production_harmony_surfaces_are_explicitly_enabled():
    for kind in ("chord", "roman_numeral", "harmonic_function"):
        assert is_product_evidence(kind)
        assert is_exposed(kind, "inspector")
        assert is_exposed(kind, "ask")


def test_structure_is_evaluation_only_and_not_exposed():
    assert capability_policy("structure")["status"] == "evaluation_only"
    assert not is_product_evidence("structure")
    assert not is_exposed("structure", "inspector")
    assert not is_exposed("structure", "annotations")
    assert not is_product_evidence("section")
    assert not is_exposed("section", "inspector")
    assert not is_product_evidence("audio_structure")
    assert not is_exposed("audio_structure", "inspector")


def test_production_capabilities_expose_inspector():
    for kind in ("key", "tempo", "time_signature", "audio_tempo", "rhythm", "melody"):
        assert is_product_evidence(kind), f"{kind} should be product evidence"
        assert is_exposed(kind, "inspector"), f"{kind} should be exposed in inspector"


def test_rhythm_subkinds_are_production_and_inspector_exposed():
    for kind in ("rhythm_density", "rhythm_rests"):
        assert is_product_evidence(kind), f"{kind} should be product evidence"
        assert is_exposed(kind, "inspector"), f"{kind} should be exposed in inspector"


def test_unknown_capability_fails_closed():
    import pytest

    with pytest.raises(KeyError, match="unregistered capability"):
        capability_policy("nonexistent_capability")


def test_inspector_exposure_matches_registry():
    """Verify that the registry exposure flags are consistent:
    production/experimental kinds with inspector exposure should be exposed,
    withheld kinds should never be exposed."""
    registry = load_capability_registry()
    for kind, policy in registry.items():
        status = policy["status"]
        exposure = policy["exposure"]
        if status == "withheld":
            assert not exposure["inspector"], f"withheld {kind} must not be inspector-exposed"
            assert not exposure["annotations"], f"withheld {kind} must not be annotations-exposed"
            assert not exposure["ask"], f"withheld {kind} must not be ask-exposed"
        if status == "evaluation_only":
            assert not exposure[
                "inspector"
            ], f"evaluation_only {kind} must not be inspector-exposed"

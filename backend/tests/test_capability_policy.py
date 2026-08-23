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
    for kind in ("cadence", "key_region"):
        assert capability_policy(kind)["status"] == "withheld"
        assert not is_product_evidence(kind)
        assert not is_exposed(kind, "inspector")
        assert not is_exposed(kind, "annotations")
        assert not is_exposed(kind, "ask")


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
    assert not is_exposed("structure", "ask")

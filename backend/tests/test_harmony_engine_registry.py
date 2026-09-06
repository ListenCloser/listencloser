import pytest

from engines.registry import HARMONY_ENGINE_REGISTRY, HarmonyEngineRegistration


def test_harmony_runtime_admission_declares_product_reachability() -> None:
    assert HARMONY_ENGINE_REGISTRY["music21"].product_reachability == "USER_REACHABLE"
    assert HARMONY_ENGINE_REGISTRY["lv_chordia"].product_reachability == "USER_REACHABLE"

    chordmini = HARMONY_ENGINE_REGISTRY["chordmini"]
    assert chordmini.product_reachability == "MISSING_UI"
    assert chordmini.follow_up_issue == 1194


def test_missing_ui_harmony_runtime_requires_focused_follow_up() -> None:
    with pytest.raises(ValueError, match="focused UI follow-up issue"):
        HarmonyEngineRegistration(
            factory=HARMONY_ENGINE_REGISTRY["music21"].factory,
            product_reachability="MISSING_UI",
        )


def test_invalid_product_reachability_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown product reachability"):
        HarmonyEngineRegistration(
            factory=HARMONY_ENGINE_REGISTRY["music21"].factory,
            product_reachability="NOT_A_PRODUCT_STATE",  # type: ignore[arg-type]
        )

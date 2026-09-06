"""Regression tests for theory capabilities that failed promotion.

Cadence and local-key-region evidence are deliberately absent from production.
The capability registry is the durable record of why they were withheld.
"""

from __future__ import annotations

import json
from pathlib import Path

import engines.theory.theory_engine as theory_engine
from engines.theory.theory_engine import TheoryEngine


def test_production_theory_keeps_withheld_capabilities_empty() -> None:
    result = TheoryEngine().analyze(
        [
            {
                "id": "c1",
                "root": "C",
                "quality": "maj",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "id": "c2",
                "root": "G",
                "quality": "maj",
                "start": 1.0,
                "end": 2.0,
            },
            {
                "id": "c3",
                "root": "C",
                "quality": "maj",
                "start": 2.0,
                "end": 4.0,
            },
        ],
        global_key="C major",
        key_source="test",
    )

    # Production-safe theory remains available.
    assert [event.numeral for event in result.roman_numerals] == ["I", "V", "I"]
    assert [event.function for event in result.harmonic_functions] == [
        "TONIC",
        "DOMINANT",
        "TONIC",
    ]

    # Rejected capabilities retain only their compatibility fields. They must
    # not silently resume emitting heuristic or fabricated-confidence evidence.
    assert result.cadences == []
    assert result.key_regions == []


def test_rejected_detector_implementations_are_not_production_symbols() -> None:
    assert not hasattr(theory_engine, "CADENCE_PATTERNS")
    assert not hasattr(theory_engine, "_detect_cadences")
    assert not hasattr(theory_engine, "_detect_key_regions")


def test_registry_preserves_why_capabilities_are_withheld() -> None:
    registry_path = Path(__file__).parents[1] / "config" / "capabilities.json"
    capabilities = json.loads(registry_path.read_text())["capabilities"]

    cadence = capabilities["cadence"]
    assert cadence["status"] == "withheld"
    assert cadence["evaluation"] == {
        "dataset": "DCML-Mozart",
        "metric": "f1",
        "value": 0.266,
    }
    assert "over-matches" in cadence["reason"]

    key_region = capabilities["key_region"]
    assert key_region["status"] == "withheld"
    assert key_region["evaluation"] == {
        "dataset": "DCML",
        "metric": "boundary_accuracy",
        "value": 0.188,
    }
    assert "placeholder" in key_region["reason"]

from __future__ import annotations

import json
from pathlib import Path

import pytest
from backend.evaluation.analysis_v3.audio_language.run import load_reference_evidence


def test_committed_reference_evidence_has_resolvable_source_refs() -> None:
    result = load_reference_evidence()
    registry = result["source_registry"]

    assert registry
    assert all(url.startswith("https://") for url in registry.values())
    for section in ("candidates", "reference_benchmarks"):
        for entry in result[section]:
            assert entry["source_refs"]
            assert set(entry["source_refs"]) <= set(registry)


def test_reference_evidence_rejects_unknown_source_ref(tmp_path: Path) -> None:
    payload = {
        "local_model_inference_performed": False,
        "source_registry": {"known": "https://example.com/reference"},
        "candidates": [{"source_refs": ["missing"]}],
        "reference_benchmarks": [{"source_refs": ["known"]}],
    }
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="unknown reference source refs"):
        load_reference_evidence(path)

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.melody import (
    MelodySongResult,
    aggregate_song_results,
    load_pop909_test_manifest,
    score_binary_note_labels,
)


def _manifest_payload() -> dict:
    return {
        "schema_version": 1,
        "dataset": "POP909",
        "split": "test",
        "split_seed": 42,
        "song_ids": [f"{song_id:03d}" for song_id in range(1, 92)],
        "source": "recovered historical training manifest",
    }


def test_pop909_manifest_rejects_seed_only_membership(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload.pop("song_ids")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="exact song_ids"):
        load_pop909_test_manifest(path)


def test_pop909_manifest_requires_exact_91_unique_ids(tmp_path: Path) -> None:
    payload = _manifest_payload()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = load_pop909_test_manifest(path)

    assert len(manifest.song_ids) == 91
    assert manifest.song_ids[0] == "001"
    assert manifest.song_ids[-1] == "091"
    assert len(manifest.sha256) == 64

    payload["song_ids"][-1] = payload["song_ids"][0]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        load_pop909_test_manifest(path)


def test_binary_melody_metrics_use_aligned_note_labels() -> None:
    metrics = score_binary_note_labels(
        reference_labels=[1, 1, 0, 0],
        predicted_labels=[1, 0, 1, 0],
    )

    assert metrics.precision == pytest.approx(0.5)
    assert metrics.recall == pytest.approx(0.5)
    assert metrics.f1 == pytest.approx(0.5)
    assert metrics.reference_positive == 2
    assert metrics.predicted_positive == 2
    assert metrics.true_positive == 1


def test_aggregate_keeps_abstentions_and_errors_in_failure_denominator() -> None:
    strong = score_binary_note_labels([1, 1, 0], [1, 1, 0])
    aggregate = aggregate_song_results(
        [
            MelodySongResult(song_id="001", status="ok", metrics=strong),
            MelodySongResult(song_id="002", status="abstained", reason="no melody output"),
            MelodySongResult(song_id="003", status="error", reason="engine exception"),
        ]
    )

    assert aggregate.song_count == 3
    assert aggregate.scored_count == 1
    assert aggregate.abstained_count == 1
    assert aggregate.error_count == 1
    assert aggregate.macro_precision == pytest.approx(1 / 3)
    assert aggregate.macro_recall == pytest.approx(1 / 3)
    assert aggregate.macro_f1 == pytest.approx(1 / 3)
    assert aggregate.failure_rate_f1_lt_0_2 == pytest.approx(2 / 3)
    assert aggregate.prediction_reference_ratio == pytest.approx(1.0)


def test_success_result_cannot_omit_metrics() -> None:
    with pytest.raises(ValueError, match="missing metrics"):
        aggregate_song_results([MelodySongResult(song_id="001", status="ok")])


def test_melody_registry_qualifies_cross_seed_historical_metric() -> None:
    registry_path = Path(__file__).resolve().parent.parent / "config" / "capabilities.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    melody = registry["capabilities"]["melody"]

    assert melody["status"] == "experimental"
    assert melody["engine"] == "lstom"
    assert melody["evaluation"]["value"] == pytest.approx(0.768)
    assert "cross-training-seed mean" in melody["evaluation"]["details"]
    assert (
        "not a newly reproduced metric for the current checkpoint"
        in melody["evaluation"]["details"]
    )

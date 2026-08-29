"""Regression tests for pulse checkpoint/data provenance safeguards."""

from __future__ import annotations

import pytest
from backend.evaluation.analysis_v3.pulse.adapters.beat_this import BeatThisAdapter
from backend.evaluation.analysis_v3.pulse.run import (
    _assess_training_overlap,
    _validate_training_overlap,
)


def test_beat_this_final0_provenance_is_explicit():
    metadata = BeatThisAdapter().metadata()

    assert metadata.checkpoint_name == "final0"
    assert metadata.upstream_repo == "https://github.com/CPJKU/beat_this"
    assert "guitarset" in metadata.training_datasets
    assert "ballroom" in metadata.training_datasets
    assert "hainsworth" in metadata.training_datasets
    assert "smc" in metadata.training_datasets
    assert metadata.held_out_datasets == ("gtzan",)


def test_training_overlap_is_not_generalization_safe():
    metadata = BeatThisAdapter().metadata()
    manifest = {
        "clips": [
            {"id": "guitar", "dataset": "GuitarSet"},
            {"id": "piano", "dataset": "maestro"},
        ]
    }

    assessment = _assess_training_overlap(metadata, manifest)

    assert assessment["datasets"] == ["guitarset", "maestro"]
    assert assessment["training_overlap"] == ["guitarset"]
    assert assessment["held_out_matches"] == []
    assert assessment["generalization_safe"] is False


def test_gtzan_is_recorded_as_held_out_for_final0():
    metadata = BeatThisAdapter().metadata()
    manifest = {"clips": [{"id": "test", "dataset": "GTZAN"}]}

    assessment = _assess_training_overlap(metadata, manifest)

    assert assessment["training_overlap"] == []
    assert assessment["held_out_matches"] == ["gtzan"]
    assert assessment["generalization_safe"] is True


def test_training_overlap_is_rejected_by_default():
    metadata = BeatThisAdapter().metadata()
    manifest = {"clips": [{"id": "train", "dataset": "guitarset"}]}

    with pytest.raises(ValueError, match="Refusing to score final0"):
        _validate_training_overlap(
            metadata,
            manifest,
            allow_training_overlap=False,
        )


def test_training_overlap_can_be_explicitly_allowed_for_probe():
    metadata = BeatThisAdapter().metadata()
    manifest = {"clips": [{"id": "train", "dataset": "guitarset"}]}

    assessment = _validate_training_overlap(
        metadata,
        manifest,
        allow_training_overlap=True,
    )

    assert assessment["training_overlap"] == ["guitarset"]
    assert assessment["generalization_safe"] is False

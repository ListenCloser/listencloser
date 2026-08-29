"""Regression tests for held-out Candombe / Beat This split provenance."""

from __future__ import annotations

import pytest
from backend.evaluation.analysis_v3.pulse.adapters.beat_this import (
    BeatThisAdapter,
    BeatThisSingleFinal0Adapter,
)
from backend.evaluation.analysis_v3.pulse.run import (
    _assess_training_overlap,
    _validate_training_overlap,
)


def test_single_final0_records_exact_split_provenance() -> None:
    metadata = BeatThisSingleFinal0Adapter().metadata()

    assert metadata.checkpoint_name == "single_final0"
    assert metadata.training_partition == "single_split_train"
    assert metadata.held_out_partition == "single_split_val"
    assert metadata.split_source == "https://github.com/CPJKU/beat_this_annotations"
    assert metadata.split_version == "v1.0"
    assert "candombe" in metadata.training_datasets
    assert "candombe_single_split_train" in metadata.training_datasets
    assert "candombe_single_split_val" in metadata.held_out_datasets


def test_single_final0_accepts_only_partition_qualified_candombe_validation_manifest() -> None:
    metadata = BeatThisSingleFinal0Adapter().metadata()
    manifest = {
        "dataset": "candombe_single_split_val",
        "clips": [
            {
                "id": "held-out",
                "dataset": "candombe_single_split_val",
                "source_dataset": "candombe",
                "split_partition": "single_split_val",
            }
        ],
    }

    assessment = _validate_training_overlap(
        metadata,
        manifest,
        allow_training_overlap=False,
    )

    assert assessment["training_overlap"] == []
    assert assessment["held_out_matches"] == ["candombe_single_split_val"]
    assert assessment["generalization_safe"] is True


def test_single_final0_rejects_unpartitioned_candombe_manifest() -> None:
    metadata = BeatThisSingleFinal0Adapter().metadata()
    manifest = {"clips": [{"id": "unknown-split", "dataset": "candombe"}]}

    assessment = _assess_training_overlap(metadata, manifest)
    assert assessment["training_overlap"] == ["candombe"]
    assert assessment["generalization_safe"] is False

    with pytest.raises(ValueError, match="Refusing to score single_final0"):
        _validate_training_overlap(
            metadata,
            manifest,
            allow_training_overlap=False,
        )


def test_single_final0_rejects_candombe_training_partition() -> None:
    metadata = BeatThisSingleFinal0Adapter().metadata()
    manifest = {"clips": [{"id": "train", "dataset": "candombe_single_split_train"}]}

    assessment = _assess_training_overlap(metadata, manifest)
    assert assessment["training_overlap"] == ["candombe_single_split_train"]
    assert assessment["held_out_matches"] == []
    assert assessment["generalization_safe"] is False

    with pytest.raises(ValueError, match="Refusing to score single_final0"):
        _validate_training_overlap(
            metadata,
            manifest,
            allow_training_overlap=False,
        )


def test_default_final0_still_rejects_candombe_as_training_overlap() -> None:
    metadata = BeatThisAdapter().metadata()
    manifest = {"clips": [{"id": "candombe", "dataset": "candombe"}]}

    assessment = _assess_training_overlap(metadata, manifest)
    assert assessment["training_overlap"] == ["candombe"]
    assert assessment["generalization_safe"] is False

    with pytest.raises(ValueError, match="Refusing to score final0"):
        _validate_training_overlap(
            metadata,
            manifest,
            allow_training_overlap=False,
        )

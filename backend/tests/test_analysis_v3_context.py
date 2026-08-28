from __future__ import annotations

import numpy as np
import pytest

from backend.evaluation.analysis_v3.context.metrics import (
    label_ranking_average_precision,
    precision_at_k,
    rank_zero_shot,
    recall_at_k,
    top_k_jaccard,
)
from backend.evaluation.analysis_v3.context.run import summarize_prior_clap


def test_multilabel_ranking_metrics() -> None:
    truth = np.asarray(
        [
            [True, False, True, False],
            [False, True, False, False],
        ]
    )
    scores = np.asarray(
        [
            [0.9, 0.8, 0.7, 0.1],
            [0.2, 0.9, 0.8, 0.1],
        ]
    )

    assert precision_at_k(truth, scores, 1) == pytest.approx(1.0)
    assert precision_at_k(truth, scores, 2) == pytest.approx(0.75)
    assert recall_at_k(truth, scores, 2) == pytest.approx(0.75)
    assert label_ranking_average_precision(truth, scores) == pytest.approx(11 / 12)


def test_recall_ignores_empty_truth_rows() -> None:
    truth = np.asarray([[False, False], [True, False]])
    scores = np.asarray([[0.9, 0.1], [0.8, 0.2]])
    assert recall_at_k(truth, scores, 1) == pytest.approx(1.0)


def test_metrics_validate_shapes_and_k() -> None:
    truth = np.asarray([[True, False]])
    scores = np.asarray([[0.8, 0.2]])
    with pytest.raises(ValueError):
        precision_at_k(truth, np.asarray([0.8, 0.2]), 1)
    with pytest.raises(ValueError):
        precision_at_k(truth, scores, 0)
    with pytest.raises(ValueError):
        recall_at_k(np.asarray([[False, False]]), scores, 1)


def test_top_k_jaccard_measures_adjacent_stability() -> None:
    rows = np.asarray(
        [
            [0.9, 0.8, 0.1, 0.0],
            [0.8, 0.7, 0.6, 0.0],
            [0.1, 0.9, 0.8, 0.0],
        ]
    )
    # {0,1}->{0,1}=1.0, then {0,1}->{1,2}=1/3.
    assert top_k_jaccard(rows, 2) == pytest.approx(2 / 3)


def test_rank_zero_shot_uses_cosine_similarity() -> None:
    audio = np.asarray([1.0, 0.0])
    text = np.asarray([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
    ranked = rank_zero_shot(audio, text, ["match", "orthogonal", "opposite"])
    assert [label for label, _score in ranked] == ["match", "orthogonal", "opposite"]
    assert ranked[0][1] == pytest.approx(1.0)
    assert ranked[-1][1] == pytest.approx(-1.0)


def test_prior_clap_summary_detects_collapsed_rankings() -> None:
    result = {
        "text_retrieval": {
            "per_query_results": [
                {
                    "ranked_results": [
                        {"audio_id": "a"},
                        {"audio_id": "b"},
                        {"audio_id": "c"},
                    ]
                },
                {
                    "ranked_results": [
                        {"audio_id": "a"},
                        {"audio_id": "b"},
                        {"audio_id": "d"},
                    ]
                },
            ]
        }
    }
    summary = summarize_prior_clap(result)
    assert summary["available"] is True
    assert summary["unique_top1"] == 1
    assert summary["unique_top1_fraction"] == pytest.approx(0.5)
    assert summary["mean_pairwise_top3_jaccard"] == pytest.approx(0.5)


def test_prior_clap_summary_handles_missing_retrieval() -> None:
    assert summarize_prior_clap({})["available"] is False

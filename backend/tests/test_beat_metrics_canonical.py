from __future__ import annotations

from evaluation.beat_metrics import compute_beat_metrics


def test_beat_metrics_match_mir_eval_default_window() -> None:
    metrics = compute_beat_metrics(
        predicted_beats=[0.0, 1.0, 2.0],
        predicted_bpm=121.5,
        predicted_downbeats=[0.0],
        reference_beats=[0.01, 1.01, 2.01],
        reference_bpm=120.0,
        reference_downbeats=[0.01],
    )

    assert metrics.beat_precision == 1.0
    assert metrics.beat_recall == 1.0
    assert metrics.beat_f1 == 1.0
    assert metrics.downbeat_f1 == 1.0
    assert metrics.matched_beat_count == 3
    assert metrics.matched_downbeat_count == 1
    assert metrics.bpm_absolute_error == 1.5


def test_downbeats_do_not_use_repository_specific_double_tolerance() -> None:
    metrics = compute_beat_metrics(
        predicted_beats=None,
        predicted_bpm=None,
        predicted_downbeats=[0.1],
        reference_beats=None,
        reference_bpm=None,
        reference_downbeats=[0.0],
        tolerance=0.07,
    )

    # mir_eval's beat convention applies the configured 70 ms window to both
    # beat and downbeat event sequences. The deleted scorer silently doubled
    # this window for downbeats, so a 100 ms miss previously counted as correct.
    assert metrics.downbeat_precision == 0.0
    assert metrics.downbeat_recall == 0.0
    assert metrics.downbeat_f1 == 0.0
    assert metrics.matched_downbeat_count == 0

"""Focused tests for the deployment-shaped AnalysisGNN admission probe."""

import hashlib
from pathlib import Path

import pytest

from evaluation.engines.analysisgnn_admission import (
    AnalysisGNNAdmissionTrial,
    run_admission_probe,
)


def _fixture_paths(tmp_path: Path):
    runtime = tmp_path / "python"
    runtime.write_text("placeholder", encoding="utf-8")
    checkpoint = tmp_path / "model.ckpt"
    checkpoint.write_bytes(b"pinned-analysisgnn-model")
    score = tmp_path / "fixture.musicxml"
    score.write_text("<score-partwise version='4.0'></score-partwise>", encoding="utf-8")
    checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    return runtime, checkpoint, score, checksum


def test_analysisgnn_probe_records_exact_assets_and_keeps_unverified_terms_blocked(tmp_path):
    runtime, checkpoint, score, checksum = _fixture_paths(tmp_path)
    calls = []

    def fake_trial_runner(**kwargs):
        calls.append(kwargs)
        return AnalysisGNNAdmissionTrial(
            elapsed_seconds=1.25 + len(calls),
            peak_child_rss_kib=123_456 + len(calls),
            observation_count=7,
            tasks=("cadence", "localkey", "romanNumeral"),
        )

    report = run_admission_probe(
        runtime_python=runtime,
        checkpoint=checkpoint,
        expected_checkpoint_sha256=checksum,
        score=score,
        artifact_terms_status="unverified",
        timeout_seconds=90.0,
        trial_runner=fake_trial_runner,
    )

    assert len(calls) == 2
    assert all(call["checkpoint_sha256"] == checksum for call in calls)
    assert all(call["runtime_python"] == runtime for call in calls)
    assert report.checkpoint_sha256 == checksum
    assert report.score_sha256 == hashlib.sha256(score.read_bytes()).hexdigest()
    assert report.artifact_terms_status == "unverified"
    assert report.process_reuse is False
    assert report.first_run.observation_count == 7
    assert report.repeat_run.observation_count == 7
    assert report.admission_ready is False
    assert "not an in-memory warm-model measurement" in report.interpretation


def test_analysisgnn_probe_only_marks_verified_permissive_checkpoint_ready(tmp_path):
    runtime, checkpoint, score, checksum = _fixture_paths(tmp_path)

    def fake_trial_runner(**_kwargs):
        return AnalysisGNNAdmissionTrial(
            elapsed_seconds=2.0,
            peak_child_rss_kib=200_000,
            observation_count=3,
            tasks=("cadence", "localkey", "romanNumeral"),
        )

    permissive = run_admission_probe(
        runtime_python=runtime,
        checkpoint=checkpoint,
        expected_checkpoint_sha256=checksum,
        score=score,
        artifact_terms_status="verified_permissive",
        trial_runner=fake_trial_runner,
    )
    restricted = run_admission_probe(
        runtime_python=runtime,
        checkpoint=checkpoint,
        expected_checkpoint_sha256=checksum,
        score=score,
        artifact_terms_status="verified_restricted",
        trial_runner=fake_trial_runner,
    )

    assert permissive.admission_ready is True
    assert restricted.admission_ready is False


def test_analysisgnn_probe_rejects_checkpoint_drift_before_inference(tmp_path):
    runtime, checkpoint, score, _ = _fixture_paths(tmp_path)
    called = False

    def fake_trial_runner(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("trial must not run after checkpoint drift")

    with pytest.raises(ValueError, match="does not match the pinned expectation"):
        run_admission_probe(
            runtime_python=runtime,
            checkpoint=checkpoint,
            expected_checkpoint_sha256="0" * 64,
            score=score,
            artifact_terms_status="verified_permissive",
            trial_runner=fake_trial_runner,
        )

    assert called is False


def test_analysisgnn_probe_rejects_empty_bounded_output(tmp_path):
    runtime, checkpoint, score, checksum = _fixture_paths(tmp_path)

    def fake_trial_runner(**_kwargs):
        return AnalysisGNNAdmissionTrial(
            elapsed_seconds=1.0,
            peak_child_rss_kib=100_000,
            observation_count=0,
            tasks=("cadence", "localkey", "romanNumeral"),
        )

    with pytest.raises(RuntimeError, match="empty bounded evidence"):
        run_admission_probe(
            runtime_python=runtime,
            checkpoint=checkpoint,
            expected_checkpoint_sha256=checksum,
            score=score,
            artifact_terms_status="verified_permissive",
            trial_runner=fake_trial_runner,
        )

"""Focused runtime-boundary tests for the AnalysisGNN challenger."""

from __future__ import annotations

import hashlib
import subprocess

import pytest

from engines.symbolic.analysisgnn import AnalysisGNNEngine, normalize_score_evidence


def _runtime_files(tmp_path):
    runtime = tmp_path / "python"
    runtime.write_text("placeholder", encoding="utf-8")
    checkpoint = tmp_path / "model.ckpt"
    checkpoint.write_bytes(b"pinned-analysisgnn-model")
    checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    return runtime, checkpoint, checksum


def test_analysisgnn_requires_explicit_checkpoint_not_wandb(tmp_path):
    runtime, _, _ = _runtime_files(tmp_path)
    engine = AnalysisGNNEngine(runtime_python=str(runtime))

    with pytest.raises(RuntimeError, match="ANALYSISGNN_CHECKPOINT_PATH"):
        engine.analyze_musicxml(b"<score-partwise/>")


def test_analysisgnn_rejects_checkpoint_hash_mismatch(tmp_path):
    runtime, checkpoint, _ = _runtime_files(tmp_path)
    engine = AnalysisGNNEngine(
        runtime_python=str(runtime),
        checkpoint_path=str(checkpoint),
        checkpoint_sha256="0" * 64,
    )

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        engine.analyze_musicxml(b"<score-partwise/>")


def test_analysisgnn_runs_local_checkpoint_offline_and_parses_csv(tmp_path, monkeypatch):
    runtime, checkpoint, checksum = _runtime_files(tmp_path)
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["env"] = kwargs["env"]
        output_dir = command[command.index("--output_dir") + 1]
        with open(f"{output_dir}/score_analysis.csv", "w", encoding="utf-8") as handle:
            handle.write("cadence,localkey,romanNumeral,onset,s_measure\nPAC,C,Ger65,12.0,5\n")
        return subprocess.CompletedProcess(command, 0, stdout="Analysis complete!", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    engine = AnalysisGNNEngine(
        runtime_python=str(runtime),
        checkpoint_path=str(checkpoint),
        checkpoint_sha256=checksum,
        device="cpu",
    )

    result = engine.analyze_musicxml(
        b"<score-partwise version='4.0'></score-partwise>",
        tasks=("cadence", "localkey", "romanNumeral"),
    )

    assert observed["command"][:3] == [
        str(runtime),
        "-m",
        "analysisgnn.inference.predict_analysis",
    ]
    assert observed["command"][observed["command"].index("--checkpoint_path") + 1] == str(
        checkpoint
    )
    assert "--wandb_artifact" not in observed["command"]
    assert observed["env"]["WANDB_MODE"] == "offline"
    assert result.predictions == [
        {
            "cadence": "PAC",
            "localkey": "C",
            "romanNumeral": "Ger65",
            "onset": "12.0",
            "s_measure": "5",
        }
    ]
    assert result.tasks == ("cadence", "localkey", "romanNumeral")
    assert result.provenance.parameters["runtime_classification"] == "INTERNAL_ONLY"
    assert result.provenance.parameters["model_license"] == "UNVERIFIED"
    assert result.provenance.parameters["checkpoint_sha256"] == checksum

    evidence = normalize_score_evidence(result)
    assert evidence.tasks == ("cadence", "localkey", "romanNumeral")
    assert evidence.observations[0].onset_beat == 12.0
    assert evidence.observations[0].measure_number == 5
    assert evidence.observations[0].labels == (
        ("cadence", "PAC"),
        ("localkey", "C"),
        ("romanNumeral", "Ger65"),
    )
    assert evidence.provenance.parameters["runtime_classification"] == "INTERNAL_ONLY"


def test_analysisgnn_score_evidence_keeps_first_product_subset_only():
    engine = AnalysisGNNEngine(
        runtime_python="/unused/runtime",
        checkpoint_path="/unused/checkpoint",
        checkpoint_sha256="1" * 64,
    )
    result = type(
        "Result",
        (),
        {
            "predictions": [
                {
                    "cadence": "PAC",
                    "localkey": "C",
                    "romanNumeral": "V7",
                    "quality": "major",
                    "onset": "8.5",
                    "s_measure": "4",
                }
            ],
            "tasks": ("cadence", "localkey", "romanNumeral", "quality"),
            "provenance": engine.provenance,
        },
    )()

    evidence = normalize_score_evidence(result)

    assert evidence.tasks == ("cadence", "localkey", "romanNumeral")
    assert evidence.observations[0].labels == (
        ("cadence", "PAC"),
        ("localkey", "C"),
        ("romanNumeral", "V7"),
    )
    assert all(task != "quality" for task, _ in evidence.observations[0].labels)


def test_analysisgnn_score_evidence_rejects_malformed_score_locator():
    engine = AnalysisGNNEngine(
        runtime_python="/unused/runtime",
        checkpoint_path="/unused/checkpoint",
        checkpoint_sha256="1" * 64,
    )
    result = type(
        "Result",
        (),
        {
            "predictions": [
                {
                    "cadence": "PAC",
                    "localkey": "C",
                    "romanNumeral": "V",
                    "onset": "not-a-number",
                    "s_measure": "4",
                }
            ],
            "tasks": ("cadence", "localkey", "romanNumeral"),
            "provenance": engine.provenance,
        },
    )()

    with pytest.raises(ValueError, match="invalid onset"):
        normalize_score_evidence(result)


def test_analysisgnn_failure_is_explicit(tmp_path, monkeypatch):
    runtime, checkpoint, checksum = _runtime_files(tmp_path)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="graph failure")

    monkeypatch.setattr(subprocess, "run", fake_run)
    engine = AnalysisGNNEngine(
        runtime_python=str(runtime),
        checkpoint_path=str(checkpoint),
        checkpoint_sha256=checksum,
    )

    with pytest.raises(RuntimeError, match="isolated runtime failed"):
        engine.analyze_musicxml(b"<score-partwise/>")

"""Focused contract tests for the #1083 Parangonar execution boundary."""

from __future__ import annotations

import json
import subprocess
from uuid import uuid4

import pytest

from domain.score_performance_alignment import (
    AlignmentProjectionPrecision,
    AlignmentRelationKind,
    AlignmentSufficiency,
    AlignmentSufficiencyPolicy,
)
from engines.alignment import parangonar as parangonar_module
from engines.alignment.parangonar import ParangonarAlignmentEngine

POLICY = AlignmentSufficiencyPolicy(
    minimum_score_fraction=0.8,
    minimum_performance_fraction=0.8,
)
MIDI = b"MThd" + b"\x00" * 10


def _runtime_python(tmp_path):
    path = tmp_path / "python"
    path.write_text("placeholder", encoding="utf-8")
    return path


def _stdout(payload):
    return "noise from child\n" + parangonar_module._OUTPUT_PREFIX + json.dumps(payload)


def _payload(*, alignment=None, failure=None):
    if alignment is None and failure is None:
        alignment = [{"label": "match", "score_id": "s1", "performance_id": "p1"}]
    return {
        "parangonar_version": "3.3.3",
        "partitura_version": "1.9.0",
        "matcher": "DualDTWNoteMatcher",
        "parameters": {
            "process_ornaments": False,
            "force_note_ids": True,
            "musicxml_validation": True,
        },
        "score_events": [{"id": "s1", "onset": 0.0}],
        "performance_events": [{"id": "p1", "onset": 0.13}],
        "alignment": alignment,
        "failure": failure,
    }


def test_align_preserves_exact_versions_and_normalizes_relation(tmp_path, monkeypatch):
    runtime_python = _runtime_python(tmp_path)
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["env"] = kwargs["env"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=_stdout(_payload()),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    score_version_id = uuid4()
    performance_version_id = uuid4()
    engine = ParangonarAlignmentEngine(runtime_python=str(runtime_python))

    result = engine.align(
        score_musicxml=b"<score-partwise/>",
        performance_midi=MIDI,
        score_version_id=score_version_id,
        performance_version_id=performance_version_id,
        sufficiency_policy=POLICY,
    )

    assert result.score_version_id == score_version_id
    assert result.performance_version_id == performance_version_id
    assert result.sufficiency is AlignmentSufficiency.sufficient
    assert result.projection_precision is AlignmentProjectionPrecision.adequate
    assert result.relations[0].kind is AlignmentRelationKind.matched
    assert result.relations[0].score_events[0].event_id == "s1"
    assert result.relations[0].performance_events[0].onset_seconds == 0.13
    assert result.method.package == "parangonar"
    assert result.method.package_version == "3.3.3"
    assert result.method.matcher == "DualDTWNoteMatcher"
    assert observed["command"][0] == str(runtime_python)
    assert observed["env"]["PYTHONNOUSERSITE"] == "1"


def test_matcher_failure_is_failed_relation_not_timestamp_fallback(tmp_path, monkeypatch):
    runtime_python = _runtime_python(tmp_path)
    payload = _payload(alignment=None, failure="IndexError: degenerate input")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout=_stdout(payload),
            stderr="",
        ),
    )
    engine = ParangonarAlignmentEngine(runtime_python=str(runtime_python))

    result = engine.align(
        score_musicxml=b"<score-partwise/>",
        performance_midi=MIDI,
        score_version_id=uuid4(),
        performance_version_id=uuid4(),
        sufficiency_policy=POLICY,
    )

    assert result.sufficiency is AlignmentSufficiency.failed
    assert result.projection_precision is AlignmentProjectionPrecision.unsupported
    assert result.failure == "IndexError: degenerate input"
    assert result.relations == ()


def test_runtime_identity_mismatch_fails_closed(tmp_path, monkeypatch):
    runtime_python = _runtime_python(tmp_path)
    payload = _payload()
    payload["parangonar_version"] = "3.4.0"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout=_stdout(payload),
            stderr="",
        ),
    )
    engine = ParangonarAlignmentEngine(runtime_python=str(runtime_python))

    with pytest.raises(RuntimeError, match="unexpected package version"):
        engine.align(
            score_musicxml=b"<score-partwise/>",
            performance_midi=MIDI,
            score_version_id=uuid4(),
            performance_version_id=uuid4(),
            sufficiency_policy=POLICY,
        )


def test_duplicate_child_event_ids_fail_closed(tmp_path, monkeypatch):
    runtime_python = _runtime_python(tmp_path)
    payload = _payload()
    payload["score_events"] = [
        {"id": "s1", "onset": 0.0},
        {"id": "s1", "onset": 1.0},
    ]
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout=_stdout(payload),
            stderr="",
        ),
    )
    engine = ParangonarAlignmentEngine(runtime_python=str(runtime_python))

    with pytest.raises(RuntimeError, match="duplicate score_events event ids"):
        engine.align(
            score_musicxml=b"<score-partwise/>",
            performance_midi=MIDI,
            score_version_id=uuid4(),
            performance_version_id=uuid4(),
            sufficiency_policy=POLICY,
        )


def test_runtime_failure_is_explicit(tmp_path, monkeypatch):
    runtime_python = _runtime_python(tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            2,
            stdout="",
            stderr="partitura parse failed",
        ),
    )
    engine = ParangonarAlignmentEngine(runtime_python=str(runtime_python))

    with pytest.raises(RuntimeError, match="partitura parse failed"):
        engine.align(
            score_musicxml=b"<score-partwise/>",
            performance_midi=MIDI,
            score_version_id=uuid4(),
            performance_version_id=uuid4(),
            sufficiency_policy=POLICY,
        )


def test_missing_runtime_and_invalid_midi_fail_before_matcher(tmp_path):
    with pytest.raises(RuntimeError, match="PARANGONAR_RUNTIME_PYTHON"):
        ParangonarAlignmentEngine(runtime_python=None).align(
            score_musicxml=b"<score-partwise/>",
            performance_midi=MIDI,
            score_version_id=uuid4(),
            performance_version_id=uuid4(),
            sufficiency_policy=POLICY,
        )

    engine = ParangonarAlignmentEngine(runtime_python=str(_runtime_python(tmp_path)))
    with pytest.raises(ValueError, match="valid MIDI header"):
        engine.align(
            score_musicxml=b"<score-partwise/>",
            performance_midi=b"not midi",
            score_version_id=uuid4(),
            performance_version_id=uuid4(),
            sufficiency_policy=POLICY,
        )

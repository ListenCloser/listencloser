"""Persistence contract for exact observed beat/downbeat coordinates."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import analyze
from domain import capabilities
from domain.models import Capability, Job


def test_handle_analyze_persists_exact_explicit_pulse_grid(monkeypatch) -> None:
    input_version_id = uuid4()
    beats = [0.11, 0.73, 1.41, 2.20, 2.86]
    # Beat This exposes downbeats as a separate array. Keep an independently
    # positioned timestamp to lock the no-invented-subset contract.
    downbeats = [0.20, 2.15]
    rhythm = {
        "beat_count": len(beats),
        "avg_note_duration": 0.2,
        "offbeat_onset_ratio": 0.25,
        "rhythmic_density": 1.0,
        "offbeat_onset_available": True,
        "note_density_over_time": [],
        "onset_density_over_time": [],
        "note_density_seconds_over_time": [],
        "onset_density_seconds_over_time": [],
        "rest_segments": [],
        "beat_phase_distribution": [],
        "beats_seconds": beats,
        "downbeats_seconds": downbeats,
        "pulse_coordinate_unit": "seconds",
    }
    analysis_result = {
        "key": None,
        "tempo": None,
        "time_signature": None,
        "chords": [],
        "roman_numerals": [],
        "cadences": [],
        "voice_leading": None,
        "phrases": [],
        "melody": None,
        "rhythm": rhythm,
        "harmony_provenance": {},
        "melody_provenance": None,
        "pulse_provenance": {"engine": "beat_this", "model_version": "test"},
    }

    persisted: list[dict] = []
    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda *_args: "owner")
    monkeypatch.setattr(capabilities, "_update_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        capabilities,
        "_lookup_version",
        lambda *_args: SimpleNamespace(id=input_version_id, metadata={}),
    )
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda *_args: b"midi")
    monkeypatch.setattr(analyze, "analyze_midi", lambda *_args, **_kwargs: analysis_result)

    def capture_insight(
        _client,
        version_id,
        kind,
        claim,
        evidence=None,
        **kwargs,
    ):
        persisted.append(
            {
                "version_id": version_id,
                "kind": kind,
                "claim": claim,
                "evidence": evidence or {},
                "engine_provenance": kwargs.get("engine_provenance"),
            }
        )
        return uuid4()

    monkeypatch.setattr(capabilities, "_create_insight", capture_insight)

    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="analyze", version="1.0"),
        input_version_ids=[input_version_id],
    )
    capabilities.handle_analyze(job, object())

    saved = next(item for item in persisted if item["kind"] == "rhythm")
    assert saved["version_id"] == input_version_id
    assert saved["evidence"]["beats_seconds"] == beats
    assert saved["evidence"]["downbeats_seconds"] == downbeats
    assert saved["evidence"]["pulse_coordinate_unit"] == "seconds"
    assert saved["engine_provenance"] == analysis_result["pulse_provenance"]

"""Regression coverage for exact Analyze → Score pulse evidence reuse."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

import analyze
from domain import capabilities
from domain import pulse_evidence_reuse as reuse
from domain.models import Capability, Insight, Job

_EXPECTED_PROVENANCE = {
    "engine": "beat_this",
    "library_version": "1.1.0",
    "model": "final0",
    "parameters": {"device": "cpu", "checkpoint": "final0"},
}


def _rhythm_insight(midi_version_id, audio_version_id, **overrides) -> Insight:
    evidence = {
        "beats_seconds": [0.1, 0.7, 1.3],
        "downbeats_seconds": [0.1],
        "pulse_coordinate_unit": "seconds",
        "pulse_bpm": 100.0,
        "pulse_source_audio_version_id": str(audio_version_id),
        "pulse_preprocessing": reuse.pulse_preprocessing_contract("m4a"),
    }
    evidence.update(overrides)
    return Insight(
        version_id=midi_version_id,
        kind="rhythm",
        claim="observed rhythm",
        evidence=evidence,
        provenance={
            "capability": "analyze",
            "capability_version": "1.0",
            "method": "heuristic",
            "engine": deepcopy(_EXPECTED_PROVENANCE),
        },
    )


def _install_repo(monkeypatch, insights) -> None:
    monkeypatch.setattr(
        reuse,
        "InsightRepo",
        lambda _client: SimpleNamespace(list_by_version=lambda _version_id, _owner_id: insights),
    )
    monkeypatch.setattr(
        reuse,
        "_current_beat_provenance",
        lambda: deepcopy(_EXPECTED_PROVENANCE),
    )


def test_load_reusable_score_pulse_requires_exact_durable_identity(monkeypatch) -> None:
    midi_version_id = uuid4()
    audio_version_id = uuid4()
    _install_repo(monkeypatch, [_rhythm_insight(midi_version_id, audio_version_id)])

    pulse = reuse.load_reusable_score_pulse(
        object(),
        midi_version_id=midi_version_id,
        audio_version_id=audio_version_id,
        owner_id="owner",
        fmt="m4a",
    )

    assert pulse == {
        "bpm": 100.0,
        "beats": [0.1, 0.7, 1.3],
        "downbeats": [0.1],
        "provenance": _EXPECTED_PROVENANCE,
    }


@pytest.mark.parametrize(
    "mutation",
    ["source", "preprocessing", "provenance", "coordinates", "bpm"],
)
def test_load_reusable_score_pulse_fails_closed_on_any_mismatch(monkeypatch, mutation) -> None:
    midi_version_id = uuid4()
    audio_version_id = uuid4()
    insight = _rhythm_insight(midi_version_id, audio_version_id)

    if mutation == "source":
        insight = insight.model_copy(
            update={
                "evidence": {
                    **insight.evidence,
                    "pulse_source_audio_version_id": str(uuid4()),
                }
            }
        )
    elif mutation == "preprocessing":
        insight = insight.model_copy(
            update={
                "evidence": {
                    **insight.evidence,
                    "pulse_preprocessing": reuse.pulse_preprocessing_contract("wav"),
                }
            }
        )
    elif mutation == "provenance":
        insight = insight.model_copy(
            update={
                "provenance": {
                    **insight.provenance,
                    "engine": {**_EXPECTED_PROVENANCE, "model": "different"},
                }
            }
        )
    elif mutation == "coordinates":
        insight = insight.model_copy(
            update={"evidence": {**insight.evidence, "beats_seconds": [0.7, 0.1]}}
        )
    elif mutation == "bpm":
        insight = insight.model_copy(update={"evidence": {**insight.evidence, "pulse_bpm": None}})

    _install_repo(monkeypatch, [insight])
    assert (
        reuse.load_reusable_score_pulse(
            object(),
            midi_version_id=midi_version_id,
            audio_version_id=audio_version_id,
            owner_id="owner",
            fmt="m4a",
        )
        is None
    )


def test_handle_analyze_persists_source_and_preprocessing_identity(monkeypatch) -> None:
    midi_version_id = uuid4()
    audio_version_id = uuid4()
    beats = [0.11, 0.73, 1.41]
    downbeats = [0.20]
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
        "pulse_provenance": deepcopy(_EXPECTED_PROVENANCE),
    }
    versions = {
        midi_version_id: SimpleNamespace(id=midi_version_id, metadata={}),
        audio_version_id: SimpleNamespace(id=audio_version_id, metadata={}),
    }
    persisted = []

    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda *_args: "owner")
    monkeypatch.setattr(capabilities, "_update_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        capabilities,
        "_lookup_version",
        lambda _client, version_id: versions[version_id],
    )
    monkeypatch.setattr(
        capabilities,
        "download_version_bytes",
        lambda version, _client: (b"midi" if version.id == midi_version_id else b"audio"),
    )
    monkeypatch.setattr(
        capabilities.music_features,
        "decode_audio_to_wav",
        lambda *_args, **_kwargs: b"wav",
    )
    monkeypatch.setattr(
        capabilities.music_features,
        "estimate_beats_with_engine",
        lambda *_args, **_kwargs: {
            "bpm": 100.0,
            "beats": beats,
            "downbeats": downbeats,
            "provenance": deepcopy(_EXPECTED_PROVENANCE),
        },
    )
    monkeypatch.setattr(
        analyze,
        "analyze_midi",
        lambda *_args, **_kwargs: analysis_result,
    )

    def capture_insight(_client, version_id, kind, claim, evidence=None, **kwargs):
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
        input_version_ids=[midi_version_id, audio_version_id],
        parameters={"fmt": "m4a"},
    )
    capabilities.handle_analyze(job, object())

    saved = next(item for item in persisted if item["kind"] == "rhythm")
    assert saved["evidence"]["pulse_source_audio_version_id"] == str(audio_version_id)
    assert saved["evidence"]["pulse_preprocessing"] == (reuse.pulse_preprocessing_contract("m4a"))
    assert saved["evidence"]["pulse_bpm"] == 100.0
    assert saved["engine_provenance"] == _EXPECTED_PROVENANCE


def _stub_score_outputs(monkeypatch, *, captured, created_metadata) -> None:
    monkeypatch.setattr(capabilities, "_update_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(capabilities, "_upload_bytes", lambda *_args, **_kwargs: None)

    def create_output(*_args, **kwargs):
        created_metadata.append(kwargs.get("metadata") or {})
        return uuid4()

    monkeypatch.setattr(capabilities, "_create_output_version", create_output)

    def notation(_midi_bytes, beat_times, **kwargs):
        captured["beat_times"] = beat_times
        captured["downbeats"] = kwargs.get("downbeats")
        return {
            "notation_midi": b"MThd-score",
            "musicxml": b"<score-partwise/>",
            "quantization_report": {},
            "provenance": {"engine": "musescore", "library_version": "test"},
        }

    monkeypatch.setattr(capabilities.music_features, "notation_with_engine", notation)
    monkeypatch.setattr(
        capabilities.music_features,
        "midi_to_wav",
        lambda *_args, **_kwargs: b"wav",
    )
    monkeypatch.setattr(
        capabilities.music_features,
        "measure_start_seconds",
        lambda *_args: [],
    )


def test_handle_score_reuses_exact_pulse_without_redownloading_audio(monkeypatch) -> None:
    midi_version_id = uuid4()
    audio_version_id = uuid4()
    versions = {
        midi_version_id: SimpleNamespace(id=midi_version_id),
        audio_version_id: SimpleNamespace(id=audio_version_id),
    }
    captured = {}
    created_metadata = []
    downloads = []

    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda *_args: "owner")
    monkeypatch.setattr(capabilities, "_resolve_work_id", lambda *_args: uuid4())
    monkeypatch.setattr(
        capabilities,
        "_lookup_version",
        lambda _client, version_id: versions[version_id],
    )

    def download(version, _client):
        downloads.append(version.id)
        if version.id == audio_version_id:
            raise AssertionError("reused Score pulse must not redownload source audio")
        return b"performance"

    monkeypatch.setattr(capabilities, "download_version_bytes", download)
    monkeypatch.setattr(
        capabilities,
        "load_reusable_score_pulse",
        lambda *_args, **_kwargs: {
            "bpm": 100.0,
            "beats": [0.1, 0.7, 1.3],
            "downbeats": [0.1],
            "provenance": deepcopy(_EXPECTED_PROVENANCE),
        },
    )

    def unexpected_beat_tracking(*_args, **_kwargs):
        raise AssertionError("reused Score pulse must not run Beat This")

    monkeypatch.setattr(
        capabilities.music_features,
        "estimate_beats_with_engine",
        unexpected_beat_tracking,
    )
    _stub_score_outputs(
        monkeypatch,
        captured=captured,
        created_metadata=created_metadata,
    )

    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="score", version="1.0"),
        input_version_ids=[midi_version_id, audio_version_id],
        parameters={"fmt": "m4a"},
    )
    capabilities.handle_score(job, object())

    assert downloads == [midi_version_id]
    assert captured["beat_times"] == [0.1, 0.7, 1.3]
    assert captured["downbeats"] == [0.1]
    assert any(item.get("estimated_tempo_bpm") == 100.0 for item in created_metadata)
    assert any(item.get("beat_provenance") == _EXPECTED_PROVENANCE for item in created_metadata)


def test_handle_score_falls_back_to_fresh_beat_tracking_on_reuse_miss(
    monkeypatch,
) -> None:
    midi_version_id = uuid4()
    audio_version_id = uuid4()
    versions = {
        midi_version_id: SimpleNamespace(id=midi_version_id),
        audio_version_id: SimpleNamespace(id=audio_version_id),
    }
    captured = {}
    created_metadata = []
    downloads = []
    beat_calls = []

    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda *_args: "owner")
    monkeypatch.setattr(capabilities, "_resolve_work_id", lambda *_args: uuid4())
    monkeypatch.setattr(
        capabilities,
        "_lookup_version",
        lambda _client, version_id: versions[version_id],
    )
    monkeypatch.setattr(
        capabilities,
        "download_version_bytes",
        lambda version, _client: downloads.append(version.id) or b"bytes",
    )
    monkeypatch.setattr(
        capabilities,
        "load_reusable_score_pulse",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        capabilities.music_features,
        "decode_audio_to_wav",
        lambda *_args, **_kwargs: b"wav",
    )

    def beat_track(*_args, **_kwargs):
        beat_calls.append(True)
        return {
            "bpm": 101.0,
            "beats": [0.2, 0.8, 1.4],
            "downbeats": [0.2],
            "provenance": deepcopy(_EXPECTED_PROVENANCE),
        }

    monkeypatch.setattr(
        capabilities.music_features,
        "estimate_beats_with_engine",
        beat_track,
    )
    _stub_score_outputs(
        monkeypatch,
        captured=captured,
        created_metadata=created_metadata,
    )

    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="score", version="1.0"),
        input_version_ids=[midi_version_id, audio_version_id],
        parameters={"fmt": "m4a"},
    )
    capabilities.handle_score(job, object())

    assert downloads == [midi_version_id, audio_version_id]
    assert beat_calls == [True]
    assert captured["beat_times"] == [0.2, 0.8, 1.4]

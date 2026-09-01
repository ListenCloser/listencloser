"""Focused regression coverage for explicit Score-engine routing."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from domain.models import Capability, Job
from engines.base import EngineProvenance, NotationResult


def test_notation_with_engine_routes_explicit_engine(monkeypatch):
    import engines.registry as registry
    import music_features

    selected = {}

    class FakeNotationEngine:
        def convert(self, midi_bytes, beat_times, **kwargs):
            return NotationResult(
                notation_midi=b"MThd-score",
                musicxml=b"<score-partwise/>",
                quantization_report={"engine": "pm2s"},
                provenance=EngineProvenance(engine="pm2s", library_version="test"),
            )

    def fake_get_notation_engine(name=None):
        selected["name"] = name
        return FakeNotationEngine()

    monkeypatch.setattr(registry, "get_notation_engine", fake_get_notation_engine)
    result = music_features.notation_with_engine(b"MThd-performance", [], engine_name="pm2s")

    assert selected["name"] == "pm2s"
    assert result["provenance"]["engine"] == "pm2s"


def test_handle_score_reads_explicit_engine_without_audio_beat_input(monkeypatch):
    from domain import capabilities

    input_version_id = uuid4()
    workflow_id = uuid4()
    work_id = uuid4()
    job = Job(
        workflow_id=workflow_id,
        capability=Capability(name="score", version="1.0"),
        input_version_ids=[input_version_id],
        parameters={"score_engine": "pm2s"},
    )
    input_version = SimpleNamespace(id=input_version_id)
    captured = {}
    created_metadata = []

    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda client, workflow: "owner-1")
    monkeypatch.setattr(capabilities, "_lookup_version", lambda client, version_id: input_version)
    monkeypatch.setattr(capabilities, "_resolve_work_id", lambda client, version_id: work_id)
    monkeypatch.setattr(capabilities, "_update_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        capabilities, "download_version_bytes", lambda *args, **kwargs: b"performance"
    )
    monkeypatch.setattr(capabilities, "_upload_bytes", lambda *args, **kwargs: None)

    def fake_create_output_version(*args, **kwargs):
        created_metadata.append(kwargs.get("metadata") or {})
        return uuid4()

    monkeypatch.setattr(capabilities, "_create_output_version", fake_create_output_version)

    def fake_notation(midi_bytes, beat_times, **kwargs):
        captured.update(kwargs)
        return {
            "notation_midi": b"MThd-score",
            "musicxml": b"<score-partwise/>",
            "quantization_report": {"engine": "pm2s"},
            "provenance": {"engine": "pm2s", "library_version": "test"},
        }

    monkeypatch.setattr(capabilities.music_features, "notation_with_engine", fake_notation)
    monkeypatch.setattr(capabilities.music_features, "midi_to_wav", lambda midi_bytes: b"wav")
    monkeypatch.setattr(capabilities.music_features, "measure_start_seconds", lambda midi_bytes: [])

    output_ids = capabilities.handle_score(job, SimpleNamespace())

    assert captured["engine_name"] == "pm2s"
    assert captured["downbeats"] is None
    assert len(output_ids) == 3
    assert any(metadata.get("score_engine_requested") == "pm2s" for metadata in created_metadata)
    assert any(
        metadata.get("provenance", {}).get("engine") == "pm2s" for metadata in created_metadata
    )

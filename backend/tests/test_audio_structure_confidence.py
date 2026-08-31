"""Guard test: audio_structure must not fabricate confidence."""

from __future__ import annotations

import types
import uuid

import domain.capabilities as capabilities
from domain.models import (
    Capability,
    Job,
    JobLifecycle,
    JobStage,
    Version,
)

OWNER_ID = "00000000-0000-4000-8000-000000000101"


def _fake_version() -> Version:
    return Version(
        artifact_id=uuid.uuid4(),
        storage_key="key.wav",
        storage_bucket="artifacts",
    )


def _fake_job(capability_name: str) -> Job:
    return Job(
        workflow_id=uuid.uuid4(),
        capability=Capability(name=capability_name, version="1.0"),
        lifecycle=JobLifecycle(current=JobStage.running),
        input_version_ids=[uuid.uuid4()],
    )


def _recording_create(captured: list[dict]):
    def _record(client, version_id, kind, claim, **kwargs) -> uuid.UUID:
        kwargs["kind"] = kind
        kwargs["claim"] = claim
        captured.append(kwargs)
        return uuid.uuid4()

    return _record


def test_audio_structure_insights_have_no_fabricated_confidence(monkeypatch):
    captured: list[dict] = []

    class _FakeStructure:
        def __init__(self):
            self.bpm = 120.0
            self.beats = [0.0, 0.5, 1.0]
            self.downbeats = [0.0]
            self.segments = [
                {"label": "Intro", "start": 0.0, "end": 2.0},
                {"label": "Verse", "start": 2.0, "end": 5.0},
            ]
            self._provenance = types.SimpleNamespace(engine="test", model="test")

        @property
        def provenance(self) -> types.SimpleNamespace:
            return self._provenance

        def evidence(self) -> dict:
            return {
                "bpm": self.bpm,
                "beat_count": len(self.beats),
                "downbeat_count": len(self.downbeats),
                "segment_count": len(self.segments),
                "engine": self._provenance.engine,
            }

    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda client, workflow_id: OWNER_ID)
    monkeypatch.setattr(capabilities, "_update_progress", lambda *a, **k: None)
    monkeypatch.setattr(capabilities, "_lookup_version", lambda client, version_id: _fake_version())
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda version, client: b"wav")
    monkeypatch.setattr(capabilities.music_features, "decode_audio_to_wav", lambda *a, **k: b"wav")
    monkeypatch.setattr(
        capabilities.music_features, "structure_with_engine", lambda wav: _FakeStructure()
    )

    class _FakeEntityRepo:
        def __init__(self, client):
            pass

        def create_many(self, entities, owner_id):
            pass

    monkeypatch.setattr(capabilities, "EntityRepo", _FakeEntityRepo)
    monkeypatch.setattr(capabilities, "_create_insight", _recording_create(captured))

    capabilities.handle_audio_structure(_fake_job("audio_structure"), None)

    kinds = {c["kind"] for c in captured}
    assert kinds == {"audio_structure", "audio_tempo", "section"}
    for c in captured:
        assert c["confidence"] is None
        assert c.get("method") is not None

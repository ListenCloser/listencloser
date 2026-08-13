"""Guard tests: describe / audio_structure must not fabricate confidence.

These capabilities write insights whose values are real measurements, but they
have no calibrated confidence model. Hard-coding a numeric confidence (0.65 /
0.7 / 0.6 / 0.8 / 0.85) masquerades a heuristic as a calibrated probability.
These tests assert the persisted confidence is ``None`` (or a genuinely derived
value for the audio key detector) and that a provenance method is set.
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest

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


def test_describe_insights_have_no_fabricated_confidence(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda client, workflow_id: OWNER_ID)
    monkeypatch.setattr(capabilities, "_update_progress", lambda *a, **k: None)
    monkeypatch.setattr(capabilities, "_lookup_version", lambda client, version_id: _fake_version())
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda version, client: b"wav")

    import soundfile as sf

    monkeypatch.setattr(sf, "read", lambda *a, **k: (np.zeros(44100, dtype=np.float32), 44100))
    monkeypatch.setattr(
        capabilities,
        "_extract_audio_descriptors",
        lambda audio, sr: {
            "bpm": 112.0,
            "key": {"tonic": "A", "mode": "minor", "confidence": 0.62},
            "loudness": -14.0,
            "spectral_centroid": 1200.0,
        },
    )
    monkeypatch.setattr(capabilities, "_create_insight", _recording_create(captured))

    capabilities.handle_describe(_fake_job("describe"), None)

    kinds = {c["kind"] for c in captured}
    assert kinds == {"bpm", "key", "loudness", "spectral_centroid"}
    for c in captured:
        if c["kind"] == "key":
            # The key detector reports a real correlation strength; that value is
            # passed through, not replaced with a fallback.
            assert c["confidence"] == pytest.approx(0.62)
        else:
            assert c["confidence"] is None
        assert c.get("method") is not None


def test_describe_key_without_detector_confidence_is_null(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda client, workflow_id: OWNER_ID)
    monkeypatch.setattr(capabilities, "_update_progress", lambda *a, **k: None)
    monkeypatch.setattr(capabilities, "_lookup_version", lambda client, version_id: _fake_version())
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda version, client: b"wav")

    import soundfile as sf

    monkeypatch.setattr(sf, "read", lambda *a, **k: (np.zeros(44100, dtype=np.float32), 44100))
    monkeypatch.setattr(
        capabilities,
        "_extract_audio_descriptors",
        lambda audio, sr: {"key": {"tonic": "A", "mode": "minor"}},
    )
    monkeypatch.setattr(capabilities, "_create_insight", _recording_create(captured))

    capabilities.handle_describe(_fake_job("describe"), None)

    key = next(c for c in captured if c["kind"] == "key")
    assert key["confidence"] is None


def test_audio_structure_insights_have_no_fabricated_confidence(monkeypatch):
    captured: list[dict] = []

    class _Segment:
        def __init__(self, label: str, start: float, end: float):
            self.label, self.start, self.end = label, start, end

    class _FakeStructure:
        def __init__(self):
            self.bpm = 120.0
            self.beats = [0.0, 0.5, 1.0]
            self.downbeats = [0.0]
            self.segments = [_Segment("Intro", 0.0, 2.0), _Segment("Verse", 2.0, 5.0)]
            self.engine = "test"
            self.model = "test"

        def evidence(self) -> dict:
            return {
                "bpm": self.bpm,
                "beat_count": len(self.beats),
                "downbeat_count": len(self.downbeats),
                "segment_count": len(self.segments),
                "engine": self.engine,
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

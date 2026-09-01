"""Pipeline smoke test against a real disposable database.

Runs the durable understand pipeline end-to-end (transcribe → score → analyze →
persist) with deterministic transcription and notation fixtures substituted for
external inference/toolchain dependencies. Persistence, jobs, schema constraints,
artifact relationships, and retrieval are all real.

This test fails on the pre-migration schema because ``handle_analyze`` persists
heuristic insights with ``confidence = NULL``.
"""

from __future__ import annotations

import io
import uuid
import wave

import pretty_midi
import pytest

import domain.capabilities as capabilities
import music_features
from domain.models import (
    Artifact,
    ArtifactKind,
    Capability,
    Job,
    JobLifecycle,
    JobStage,
    Project,
    Version,
    Work,
    Workflow,
    WorkflowKind,
)
from domain.repositories import (
    ArtifactRepo,
    JobRepo,
    ProjectRepo,
    VersionRepo,
    WorkflowRepo,
    WorkRepo,
)
from engines.base import EngineProvenance, TranscriptionResult

OWNER_ID = "00000000-0000-4000-8000-000000000101"

pytestmark = pytest.mark.real_stack


def _fixture_midi() -> bytes:
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    instrument = pretty_midi.Instrument(program=0)
    for i, pitch in enumerate([60, 64, 67, 71, 72, 67, 64, 60]):
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=pitch, start=i * 0.5, end=i * 0.5 + 0.4)
        )
    pm.instruments.append(instrument)
    buffer = io.BytesIO()
    pm.write(buffer)
    return buffer.getvalue()


def _fixture_wav() -> bytes:
    """Return deterministic valid PCM without depending on a system synthesizer."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(b"\x00\x00" * 22050)
    return buffer.getvalue()


def _fixture_transcription() -> TranscriptionResult:
    midi = _fixture_midi()
    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi))
    notes = [
        {"pitch": n.pitch, "start": n.start, "end": n.end, "velocity": n.velocity}
        for inst in pm.instruments
        for n in inst.notes
    ]
    return TranscriptionResult(
        midi=midi,
        wav=_fixture_wav(),
        notes=notes,
        num_notes=len(notes),
        cleanup_report={"profile": "fixture"},
        provenance=EngineProvenance(engine="fixture", library_version="test"),
    )


def _fixture_notation(midi_bytes: bytes, beat_times: list[float], **kwargs) -> dict:
    """Return deterministic notation artifacts without requiring MuseScore in DB CI."""
    return {
        "notation_midi": midi_bytes,
        "musicxml": (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<score-partwise version="4.0"><part-list/></score-partwise>'
        ),
        "quantization_report": {"profile": "fixture"},
        "provenance": {"engine": "fixture", "library_version": "test"},
    }


class _FixtureEngine:
    def transcribe(self, audio_bytes, fmt="wav", **kwargs):
        return _fixture_transcription()


def _seed(sb):
    project = ProjectRepo(sb).create(
        Project(owner_id=OWNER_ID, name=f"it-pipeline-{uuid.uuid4().hex[:8]}")
    )
    work = WorkRepo(sb).create(Work(project_id=project.id, title="pipeline smoke"), OWNER_ID)
    artifact = ArtifactRepo(sb).create(
        Artifact(work_id=work.id, kind=ArtifactKind.audio_original), OWNER_ID
    )
    version = VersionRepo(sb).create(
        Version(
            artifact_id=artifact.id,
            storage_key=f"it/{uuid.uuid4().hex}.wav",
            storage_bucket="artifacts",
        ),
        OWNER_ID,
    )
    workflow = WorkflowRepo(sb).create(
        Workflow(project_id=project.id, kind=WorkflowKind.understand), OWNER_ID
    )
    return project, work, version, workflow


def test_understand_pipeline_persists_full_bundle(sb, monkeypatch):
    project, work, version, workflow = _seed(sb)

    monkeypatch.setattr(
        music_features, "get_transcription_engine_for_job", lambda *a, **k: _FixtureEngine()
    )
    monkeypatch.setattr(music_features, "structure_with_engine", lambda wav: None)
    # This is a persistence smoke test, not an external-binary integration test.
    # Keep the durable score path real while replacing MuseScore conversion with
    # deterministic notation bytes, just as transcription inference is stubbed.
    monkeypatch.setattr(music_features, "notation_with_engine", _fixture_notation)
    monkeypatch.setattr(
        music_features, "midi_to_wav", lambda *_args, sr=44100, **_kwargs: _fixture_wav()
    )
    # The fixture already supplies valid WAV bytes; skip the ffmpeg decode so the
    # smoke test exercises persistence without an external audio toolchain.
    monkeypatch.setattr(
        music_features, "decode_audio_to_wav", lambda audio_bytes, fmt="wav": audio_bytes
    )

    def _fake_download(version_obj, client):
        kind = capabilities._artifact_kind_for_version(client, version_obj.id)
        if kind == ArtifactKind.audio_original:
            return _fixture_wav()
        return _fixture_midi()

    monkeypatch.setattr(capabilities, "download_version_bytes", _fake_download)

    job = Job(
        workflow_id=workflow.id,
        capability=Capability(name="understand", version="1.0"),
        lifecycle=JobLifecycle(current=JobStage.running),
        input_version_ids=[version.id],
    )
    JobRepo(sb).create(job, OWNER_ID)

    outputs = capabilities.handle_understand(job, sb)
    assert outputs

    artifacts = sb.table("artifacts").select("*").eq("work_id", str(work.id)).execute().data
    kinds = {row["kind"] for row in artifacts}
    for expected in (
        "audio_original",
        "midi_performance",
        "audio_rendered",
        "midi_corrected",
        "musicxml_score",
        "rendered_score",
    ):
        assert expected in kinds, f"missing artifact kind {expected}: {sorted(kinds)}"

    def _version_for(kind: str) -> dict:
        artifact = next(row for row in artifacts if row["kind"] == kind)
        versions = (
            sb.table("artifact_versions")
            .select("*")
            .eq("artifact_id", artifact["id"])
            .execute()
            .data
        )
        assert versions, f"no version for {kind}"
        return versions[0]

    notation_version = _version_for("midi_corrected")
    performance_version = _version_for("midi_performance")
    transcription_version = _version_for("audio_rendered")
    score_version = _version_for("rendered_score")

    # rendered_score is derived from the notation representation, never the
    # performance MIDI render, and is a distinct source id from the transcription.
    assert (
        score_version["parent_version_id"] == notation_version["id"]
    ), "rendered_score must be parented from the notation MIDI, not the performance MIDI"
    assert score_version["parent_version_id"] != performance_version["id"]
    assert score_version["id"] != transcription_version["id"]

    # Score playback carries the measure grid used for animated following.
    measure_starts = score_version["metadata"].get("measure_starts_seconds")
    assert measure_starts, "rendered_score missing measure_starts_seconds"
    assert measure_starts[0] == 0.0

    midi_version_id = performance_version["id"]

    insights = (
        sb.table("insights").select("*").eq("version_id", str(midi_version_id)).execute().data
    )
    assert insights, "analysis persisted no insights"
    assert any(
        row["confidence"] is None for row in insights
    ), "heuristic insights did not round-trip a NULL confidence"

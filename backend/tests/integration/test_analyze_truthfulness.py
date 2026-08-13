"""Real-database integration test for truthful analysis.

Verifies that a basic_pitch-derived MIDI (which carries 120 BPM / 4/4
placeholders) does not surface tempo or time-signature insights as detected
facts, while supported evidence (key, rhythm, melody) still persists.
"""

from __future__ import annotations

import io
import uuid

import pretty_midi
import pytest

import domain.capabilities as capabilities
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
    InsightRepo,
    JobRepo,
    ProjectRepo,
    VersionRepo,
    WorkflowRepo,
    WorkRepo,
)

OWNER_ID = "00000000-0000-4000-8000-000000000101"

pytestmark = pytest.mark.integration


def _midi_bytes() -> bytes:
    """A MIDI with tempo 120 and 4/4 (the basic_pitch placeholder signature)."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    pm.time_signature_changes.append(
        pretty_midi.TimeSignature(numerator=4, denominator=4, time=0.0)
    )
    inst = pretty_midi.Instrument(program=0)
    for i, pitch in enumerate([60, 64, 67, 71, 72, 67, 64, 60]):
        inst.notes.append(
            pretty_midi.Note(velocity=80, pitch=pitch, start=i * 0.5, end=i * 0.5 + 0.4)
        )
    pm.instruments.append(inst)
    buf = io.BytesIO()
    pm.write(buf)
    return buf.getvalue()


def _seed_midi_version(sb, engine: str) -> Version:
    project = ProjectRepo(sb).create(
        Project(owner_id=OWNER_ID, name=f"it-analyze-{uuid.uuid4().hex[:8]}")
    )
    work = WorkRepo(sb).create(Work(project_id=project.id, title="truthful analyze"), OWNER_ID)
    artifact = ArtifactRepo(sb).create(
        Artifact(work_id=work.id, kind=ArtifactKind.midi_performance), OWNER_ID
    )
    workflow = WorkflowRepo(sb).create(
        Workflow(project_id=project.id, kind=WorkflowKind.understand), OWNER_ID
    )
    version = VersionRepo(sb).create(
        Version(
            artifact_id=artifact.id,
            storage_key=f"it/{uuid.uuid4().hex}.mid",
            storage_bucket="artifacts",
            metadata={"provenance": {"engine": engine, "library_version": "test"}},
        ),
        OWNER_ID,
    )
    return version, workflow


def _run_analyze(sb, monkeypatch, version, workflow):
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda v, c: _midi_bytes())
    job = Job(
        workflow_id=workflow.id,
        capability=Capability(name="analyze", version="1.0"),
        lifecycle=JobLifecycle(current=JobStage.running),
        input_version_ids=[version.id],
    )
    JobRepo(sb).create(job, OWNER_ID)
    capabilities.handle_analyze(job, sb)
    return InsightRepo(sb).list_by_version(version.id, OWNER_ID)


def test_basic_pitch_pulse_defaults_not_surfaced(sb, monkeypatch):
    version, workflow = _seed_midi_version(sb, engine="basic_pitch")
    insights = _run_analyze(sb, monkeypatch, version, workflow)
    kinds = {i.kind for i in insights}
    assert insights, "analysis persisted no insights"
    assert "tempo" not in kinds, "default 120 BPM must not surface as detected"
    assert "time_signature" not in kinds, "default 4/4 must not surface as detected"
    # Supported evidence should still persist (key detection, rhythm, melody).
    assert "key" in kinds
    assert "rhythm" in kinds
    assert "melody" in kinds


def test_non_basic_pitch_pulse_is_surfaced(sb, monkeypatch):
    version, workflow = _seed_midi_version(sb, engine="fixture")
    insights = _run_analyze(sb, monkeypatch, version, workflow)
    kinds = {i.kind for i in insights}
    # A non-basic_pitch MIDI's explicit tempo/meter is genuine evidence.
    assert "tempo" in kinds
    assert "time_signature" in kinds

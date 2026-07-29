from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from domain.models import (
    Alignment,
    AlignmentKind,
    Artifact,
    ArtifactKind,
    Capability,
    ChordEntity,
    Entity,
    EntityKind,
    Insight,
    Job,
    JobLifecycle,
    JobStage,
    NoteEntity,
    Project,
    Selection,
    Span,
    TimelineUnit,
    Version,
    Work,
    Workflow,
    WorkflowKind,
)


def _make_project() -> Project:
    return Project(owner_id="user-1", name="My Project")


def _make_work(project: Project) -> Work:
    return Work(project_id=project.id, title="My Piece")


def _make_artifact(work: Work, kind: ArtifactKind = ArtifactKind.audio_original) -> Artifact:
    return Artifact(work_id=work.id, kind=kind)


def _make_version(artifact: Artifact) -> Version:
    return Version(
        artifact_id=artifact.id,
        storage_key=f"versions/{uuid4()}.wav",
        storage_bucket="artifacts",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )


class TestProject:
    def test_create_minimal(self):
        p = Project(owner_id="u1", name="Test")
        assert isinstance(p.id, UUID)
        assert p.owner_id == "u1"
        assert p.name == "Test"
        assert p.description == ""
        assert p.archived_at is None

    def test_immutable(self):
        p = Project(owner_id="u1", name="Test")
        with pytest.raises(ValidationError):
            p.name = "Changed"

    def test_serialize_deserialize(self):
        p = _make_project()
        data = p.model_dump(mode="json")
        restored = Project.model_validate(data)
        assert restored == p

    def test_json_schema_roundtrip(self):
        p = _make_project()
        js = p.model_dump_json()
        back = Project.model_validate_json(js)
        assert back == p


class TestWork:
    def test_create(self, project: Project):
        w = Work(project_id=project.id, title="Etude No.1")
        assert w.project_id == project.id
        assert w.title == "Etude No.1"

    def test_immutable(self, work: Work):
        with pytest.raises(ValidationError):
            work.title = "Changed"

    def test_serialize(self, work: Work):
        data = work.model_dump(mode="json")
        back = Work.model_validate(data)
        assert back == work


class TestArtifact:
    def test_create(self, work: Work):
        a = Artifact(work_id=work.id, kind=ArtifactKind.audio_original)
        assert a.work_id == work.id
        assert a.kind == ArtifactKind.audio_original

    def test_all_kinds_valid(self):
        for kind in ArtifactKind:
            a = Artifact(work_id=uuid4(), kind=kind)
            assert a.kind == kind

    def test_immutable(self, artifact: Artifact):
        with pytest.raises(ValidationError):
            artifact.kind = ArtifactKind.stems


class TestVersion:
    def test_create_minimal(self, artifact: Artifact):
        v = _make_version(artifact)
        assert v.artifact_id == artifact.id
        assert isinstance(v.id, UUID)
        assert v.parent_version_id is None
        assert v.lineage == []

    def test_lineage_chain(self, artifact: Artifact):
        v1 = _make_version(artifact)
        v2 = Version(
            artifact_id=artifact.id,
            parent_version_id=v1.id,
            lineage=[v1.id],
            storage_key="versions/v2.wav",
            storage_bucket="artifacts",
        )
        assert v2.parent_version_id == v1.id
        assert v2.lineage == [v1.id]

    def test_immutable(self, version: Version):
        with pytest.raises(ValidationError):
            version.storage_key = "changed"

    def test_serialize(self, version: Version):
        data = version.model_dump(mode="json")
        back = Version.model_validate(data)
        assert back == version

    def test_provenance_fields(self, artifact: Artifact):
        job_id = uuid4()
        v = Version(
            artifact_id=artifact.id,
            storage_key="k",
            storage_bucket="b",
            created_by="agent-1",
            produced_by_job_id=job_id,
            byte_size=1024,
            label="Corrected",
        )
        assert v.produced_by_job_id == job_id
        assert v.created_by == "agent-1"
        assert v.byte_size == 1024
        assert v.label == "Corrected"


class TestEntity:
    def test_note_entity(self, version: Version):
        note = NoteEntity(pitch=60, start_seconds=0.0, end_seconds=0.5, velocity=80)
        e = Entity(
            version_id=version.id,
            kind=EntityKind.note,
            span=Span(start_seconds=0.0, end_seconds=0.5),
            note=note,
        )
        assert e.kind == EntityKind.note
        assert e.note.pitch == 60

    def test_chord_entity(self, version: Version):
        chord = ChordEntity(
            root="C", quality="major", start_seconds=0.0, end_seconds=2.0
        )
        e = Entity(
            version_id=version.id,
            kind=EntityKind.chord,
            span=Span(start_seconds=0.0, end_seconds=2.0),
            chord=chord,
        )
        assert e.chord.root == "C"

    def test_span_beat_measures(self):
        s = Span(start_beat=1.0, end_beat=4.0, start_measure=1, end_measure=1)
        assert s.start_beat == 1.0
        assert s.end_measure == 1

    def test_immutable(self, entity: Entity):
        with pytest.raises(ValidationError):
            entity.kind = EntityKind.cadence


class TestInsight:
    def test_create(self, version: Version):
        i = Insight(
            version_id=version.id,
            kind="key_signature",
            claim="C major",
            span=Span(start_seconds=0.0, end_seconds=10.0),
            confidence=0.95,
            evidence={"method": "krumhansl_schmuckler"},
            provenance={"library": "music21", "version": "10.0"},
        )
        assert i.confidence == 0.95
        assert i.claim == "C major"

    def test_confidence_bounds(self, version: Version):
        with pytest.raises(ValidationError):
            Insight(version_id=version.id, kind="x", claim="x", confidence=1.5)
        with pytest.raises(ValidationError):
            Insight(version_id=version.id, kind="x", claim="x", confidence=-0.1)

    def test_immutable(self, insight: Insight):
        with pytest.raises(ValidationError):
            insight.confidence = 0.5

    def test_serialize(self, insight: Insight):
        data = insight.model_dump(mode="json")
        back = Insight.model_validate(data)
        assert back == insight


class TestAlignment:
    def test_create(self, version: Version, artifact: Artifact):
        target = _make_version(artifact)
        a = Alignment(
            version_id=version.id,
            target_version_id=target.id,
            kind=AlignmentKind.timeline,
            source_unit=TimelineUnit.seconds,
            target_unit=TimelineUnit.beats,
        )
        assert a.kind == AlignmentKind.timeline

    def test_confidence_bounds(self, version: Version):
        with pytest.raises(ValidationError):
            Alignment(
                version_id=version.id,
                target_version_id=version.id,
                kind=AlignmentKind.timeline,
                source_unit=TimelineUnit.seconds,
                target_unit=TimelineUnit.beats,
                confidence=1.5,
            )

    def test_immutable(self, alignment: Alignment):
        with pytest.raises(ValidationError):
            alignment.confidence = 0.3


class TestJob:
    def test_create(self):
        cap = Capability(
            name="transcribe",
            version="1.0",
            accepted_input_kinds=[ArtifactKind.audio_original],
            produces_output_kinds=[ArtifactKind.midi_performance],
        )
        j = Job(workflow_id=uuid4(), capability=cap)
        assert j.lifecycle.current == JobStage.queued
        assert j.lifecycle.retry_count == 0

    def test_lifecycle_stages(self):
        cap = Capability(name="transcribe", version="1.0")
        lifecycle = JobLifecycle(
            current=JobStage.running,
            progress=0.5,
            started_at=datetime.now().astimezone(),
        )
        j = Job(workflow_id=uuid4(), capability=cap, lifecycle=lifecycle)
        assert j.lifecycle.current == JobStage.running
        assert j.lifecycle.progress == 0.5

    def test_progress_bounds(self):
        with pytest.raises(ValidationError):
            JobLifecycle(progress=1.5)
        with pytest.raises(ValidationError):
            JobLifecycle(progress=-0.1)

    def test_immutable(self, job: Job):
        with pytest.raises(ValidationError):
            job.lifecycle = JobLifecycle(current=JobStage.failed)

    def test_cache_key(self):
        cap = Capability(name="transcribe", version="1.0")
        j = Job(workflow_id=uuid4(), capability=cap, cache_key="md5:abc123")
        assert j.cache_key == "md5:abc123"


class TestWorkflow:
    def test_create(self, project: Project):
        wf = Workflow(project_id=project.id, kind=WorkflowKind.understand)
        assert wf.kind == WorkflowKind.understand

    def test_all_kinds(self, project: Project):
        for kind in WorkflowKind:
            wf = Workflow(project_id=project.id, kind=kind)
            assert wf.kind == kind


class TestSelection:
    def test_time_selection(self):
        s = Selection(time_start_seconds=0.0, time_end_seconds=4.0)
        assert s.time_start_seconds == 0.0
        assert s.beat_start is None

    def test_measure_selection(self):
        s = Selection(measure_start=1, measure_end=4)
        assert s.measure_start == 1
        assert s.measure_end == 4

    def test_immutable(self):
        s = Selection(time_start_seconds=1.0)
        with pytest.raises(ValidationError):
            s.time_start_seconds = 2.0


class TestContractCompatibility:
    def test_version_can_reference_job(self, artifact: Artifact, job: Job):
        v = Version(
            artifact_id=artifact.id,
            storage_key="k",
            storage_bucket="b",
            produced_by_job_id=job.id,
            created_by="worker-1",
        )
        assert v.produced_by_job_id == job.id

    def test_insight_can_reference_job(self, version: Version, job: Job):
        i = Insight(
            version_id=version.id,
            kind="key",
            claim="C major",
            produced_by_job_id=job.id,
        )
        assert i.produced_by_job_id == job.id

    def test_entity_can_reference_note_and_chord(self, version: Version):
        note = NoteEntity(pitch=60, start_seconds=0.0, end_seconds=0.5)
        e = Entity(
            version_id=version.id,
            kind=EntityKind.note,
            span=Span(start_seconds=0.0, end_seconds=0.5),
            note=note,
        )
        assert e.note.pitch == 60
        assert e.chord is None

    def test_project_to_work_to_artifact_to_version_chain(self):
        p = _make_project()
        w = _make_work(p)
        a = _make_artifact(w)
        v = _make_version(a)

        assert v.artifact_id == a.id
        assert a.work_id == w.id
        assert w.project_id == p.id


@pytest.fixture
def project() -> Project:
    return _make_project()


@pytest.fixture
def work(project: Project) -> Work:
    return _make_work(project)


@pytest.fixture
def artifact(work: Work) -> Artifact:
    return _make_artifact(work)


@pytest.fixture
def version(artifact: Artifact) -> Version:
    return _make_version(artifact)


@pytest.fixture
def entity(version: Version) -> Entity:
    note = NoteEntity(pitch=60, start_seconds=0.0, end_seconds=0.5)
    return Entity(
        version_id=version.id,
        kind=EntityKind.note,
        span=Span(start_seconds=0.0, end_seconds=0.5),
        note=note,
    )


@pytest.fixture
def insight(version: Version) -> Insight:
    return Insight(
        version_id=version.id,
        kind="key_signature",
        claim="C major",
        span=Span(start_seconds=0.0, end_seconds=10.0),
    )


@pytest.fixture
def alignment(version: Version, artifact: Artifact) -> Alignment:
    target = _make_version(artifact)
    return Alignment(
        version_id=version.id,
        target_version_id=target.id,
        kind=AlignmentKind.timeline,
        source_unit=TimelineUnit.seconds,
        target_unit=TimelineUnit.beats,
    )


@pytest.fixture
def job() -> Job:
    cap = Capability(name="transcribe", version="1.0")
    return Job(workflow_id=uuid4(), capability=cap)




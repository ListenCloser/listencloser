from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> UUID:
    return uuid4()


def utc_now() -> datetime:
    return datetime.now().astimezone()


class Project(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    owner_id: str
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    archived_at: datetime | None = None


class Work(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    project_id: UUID
    title: str
    composer: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ArtifactKind(str, Enum):
    audio_original = "audio_original"
    audio_enhanced = "audio_enhanced"
    midi_performance = "midi_performance"
    midi_corrected = "midi_corrected"
    musicxml_score = "musicxml_score"
    rendered_score = "rendered_score"
    stems = "stems"
    analysis_report = "analysis_report"


class Artifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    work_id: UUID
    kind: ArtifactKind
    mime_type: str = "application/octet-stream"
    created_at: datetime = Field(default_factory=utc_now)


class Version(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    artifact_id: UUID
    parent_version_id: UUID | None = None
    lineage: list[UUID] = Field(default_factory=list)
    storage_key: str
    storage_bucket: str
    byte_size: int | None = None
    sha256: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str | None = None
    produced_by_job_id: UUID | None = None
    label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityKind(str, Enum):
    note = "note"
    chord = "chord"
    beat = "beat"
    measure = "measure"
    phrase = "phrase"
    section = "section"
    cadence = "cadence"
    motif = "motif"


class NoteEntity(BaseModel):
    model_config = ConfigDict(frozen=True)

    pitch: int
    start_seconds: float
    end_seconds: float
    velocity: int = 64
    voice: int = 0


class ChordEntity(BaseModel):
    model_config = ConfigDict(frozen=True)

    root: str
    quality: str
    bass: str | None = None
    start_seconds: float
    end_seconds: float


class Cadence(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    chords: list[str] = Field(default_factory=list)
    position_seconds: float


class Span(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_seconds: float | None = None
    end_seconds: float | None = None
    start_beat: float | None = None
    end_beat: float | None = None
    start_measure: int | None = None
    end_measure: int | None = None


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    version_id: UUID
    kind: EntityKind
    span: Span = Field(default_factory=Span)
    note: NoteEntity | None = None
    chord: ChordEntity | None = None
    cadence: Cadence | None = None
    label: str = ""


class Insight(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    version_id: UUID
    kind: str
    claim: str
    span: Span = Field(default_factory=Span)
    entity_ids: list[UUID] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str | None = None
    produced_by_job_id: UUID | None = None


class AlignmentKind(str, Enum):
    timeline = "timeline"
    version = "version"
    performance = "performance"


class TimelineUnit(str, Enum):
    seconds = "seconds"
    samples = "samples"
    beats = "beats"
    measures = "measures"
    ticks = "ticks"
    score_position = "score_position"


class Timeline(BaseModel):
    model_config = ConfigDict(frozen=True)

    bpm: float = 120.0
    time_signature_numerator: int = 4
    time_signature_denominator: int = 4
    sample_rate: int = 44100
    ticks_per_quarter: int = 480


class Alignment(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    version_id: UUID
    target_version_id: UUID
    kind: AlignmentKind
    source_unit: TimelineUnit
    target_unit: TimelineUnit
    mapping_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    created_at: datetime = Field(default_factory=utc_now)
    produced_by_job_id: UUID | None = None


class Selection(BaseModel):
    model_config = ConfigDict(frozen=True)

    time_start_seconds: float | None = None
    time_end_seconds: float | None = None
    beat_start: float | None = None
    beat_end: float | None = None
    measure_start: int | None = None
    measure_end: int | None = None
    note_indices: list[int] = Field(default_factory=list)
    entity_ids: list[UUID] = Field(default_factory=list)


class WorkflowKind(str, Enum):
    understand = "understand"
    correct = "correct"
    compare = "compare"
    create = "create"
    export = "export"


class Capability(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    accepted_input_kinds: list[ArtifactKind] = Field(default_factory=list)
    produces_output_kinds: list[ArtifactKind] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    failure_modes: list[str] = Field(default_factory=list)


class Workflow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    project_id: UUID
    kind: WorkflowKind
    target_version_id: UUID | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class JobStage(str, Enum):
    queued = "queued"
    claimed = "claimed"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class ProcessingStatus(BaseModel):
    stage: JobStage
    progress: float = Field(ge=0.0, le=1.0, default=0.0)
    message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobLifecycle(BaseModel):
    current: JobStage = JobStage.queued
    progress: float = Field(ge=0.0, le=1.0, default=0.0)
    message: str = ""
    stages: list[ProcessingStatus] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    lease_expires_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Job(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    workflow_id: UUID
    capability: Capability
    lifecycle: JobLifecycle = Field(default_factory=JobLifecycle)
    input_version_ids: list[UUID] = Field(default_factory=list)
    output_version_ids: list[UUID] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    cache_key: str | None = None
    error: str | None = None
    error_details: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str | None = None

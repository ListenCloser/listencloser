"""Publication integration for supplied-text alignment without model download."""

from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import domain.lyrics_alignment_capability as capability
from domain.lyrics_alignment_report import (
    LyricsAlignmentMethod,
    LyricsAlignmentReport,
    LyricsWordSpan,
)
from domain.models import Artifact, ArtifactKind, Capability, Job, Version


class _Query:
    def update(self, _payload):
        return self

    def eq(self, _column, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=[{"ok": True}])


class _Bucket:
    def __init__(self, audio_bytes: bytes):
        self.audio_bytes = audio_bytes
        self.uploads: dict[str, bytes] = {}

    def download(self, _key: str) -> bytes:
        return self.audio_bytes

    def upload(self, key: str, data: bytes, _options: dict) -> None:
        self.uploads[key] = data


class _Storage:
    def __init__(self, audio_bytes: bytes):
        self.bucket = _Bucket(audio_bytes)

    def from_(self, _bucket: str) -> _Bucket:
        return self.bucket


class _Client:
    def __init__(self, audio_bytes: bytes):
        self.storage = _Storage(audio_bytes)

    def table(self, _name: str) -> _Query:
        return _Query()


def test_capability_publishes_exact_parent_and_provenance(monkeypatch) -> None:
    owner = "owner-1"
    work_id = uuid4()
    source_artifact = Artifact(
        work_id=work_id,
        kind=ArtifactKind.audio_original,
        mime_type="audio/wav",
    )
    audio_bytes = b"exact-audio-version-bytes"
    source_version = Version(
        artifact_id=source_artifact.id,
        storage_key="source.wav",
        storage_bucket="artifacts",
        sha256=sha256(audio_bytes).hexdigest(),
        label="source.wav",
        created_by=owner,
    )
    created_versions: list[Version] = []
    created_artifacts: list[Artifact] = []

    class _VersionRepo:
        def __init__(self, _client):
            pass

        def get(self, version_id, _owner):
            return source_version if version_id == source_version.id else None

        def create(self, version, _owner):
            created_versions.append(version)
            return version

    class _ArtifactRepo:
        def __init__(self, _client):
            pass

        def get(self, artifact_id, _owner):
            return source_artifact if artifact_id == source_artifact.id else None

        def create(self, artifact, _owner):
            created_artifacts.append(artifact)
            return artifact

    def _align(_audio_bytes: bytes, **kwargs):
        return LyricsAlignmentReport(
            source_audio_version_id=kwargs["source_audio_version_id"],
            source_audio_artifact_id=kwargs["source_audio_artifact_id"],
            source_audio_sha256=kwargs["source_audio_sha256"],
            source_text=kwargs["source_text"],
            source_text_sha256=kwargs["source_text_sha256"],
            text_source=kwargs["text_source"],
            text_source_reference=kwargs["text_source_reference"],
            method=LyricsAlignmentMethod(
                torchaudio_version="2.6.0",
                torch_version="2.6.0",
            ),
            status="partial",
            spans=[
                LyricsWordSpan(
                    index=0,
                    text="hello",
                    char_start=0,
                    char_end=5,
                    status="aligned",
                    start_seconds=0.1,
                    end_seconds=0.5,
                    score=0.9,
                ),
                LyricsWordSpan(
                    index=1,
                    text="world",
                    char_start=6,
                    char_end=11,
                    status="ambiguous",
                    start_seconds=0.6,
                    end_seconds=1.0,
                    score=0.4,
                    reason="low_ctc_alignment_score",
                ),
            ],
        )

    monkeypatch.setattr(capability, "VersionRepo", _VersionRepo)
    monkeypatch.setattr(capability, "ArtifactRepo", _ArtifactRepo)
    monkeypatch.setattr(capability, "align_supplied_text_to_audio", _align)

    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="lyrics_alignment", version="1.0"),
        input_version_ids=[source_version.id],
        parameters={
            "text": "hello world",
            "text_source": "user_provided",
            "language": "en",
            "ambiguity_threshold": 0.55,
        },
        created_by=owner,
    )
    client = _Client(audio_bytes)

    output_ids = capability.handle_lyrics_alignment(job, client)

    assert len(created_artifacts) == 1
    assert created_artifacts[0].kind == ArtifactKind.analysis_report
    assert len(created_versions) == 1
    output = created_versions[0]
    assert output_ids == [str(output.id)]
    assert output.parent_version_id == source_version.id
    assert output.lineage == [source_version.id]
    assert output.produced_by_job_id == job.id
    assert output.metadata["source_version_id"] == str(source_version.id)
    assert output.metadata["source_audio_sha256"] == source_version.sha256
    assert output.metadata["source_text_sha256"] == sha256(b"hello world").hexdigest()
    assert output.metadata["alignment_status"] == "partial"
    assert output.metadata["ambiguous_span_count"] == 1
    assert output.metadata["failed_span_count"] == 0
    assert output.metadata["transcription_used"] is False
    assert output.metadata["frontend_exposure"] == "deferred"
    assert client.storage.bucket.uploads

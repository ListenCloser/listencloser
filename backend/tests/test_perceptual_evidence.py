from __future__ import annotations

import io
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest
import soundfile as sf

from domain import perceptual_capability
from domain.models import Artifact, ArtifactKind, Capability, Job, Version
from perceptual_evidence import (
    CANONICAL_SAMPLE_RATE,
    PREPROCESSING_VERSION,
    PerceptualEvidenceReport,
    build_perceptual_evidence_report,
    canonicalize_audio_bytes,
    extract_measured_perceptual_series,
)


def _sine(
    frequency_hz: float,
    duration_seconds: float,
    *,
    sample_rate: int = CANONICAL_SAMPLE_RATE,
    amplitude: float = 1.0,
) -> np.ndarray:
    times = np.arange(int(sample_rate * duration_seconds), dtype=float) / sample_rate
    return amplitude * np.sin(2.0 * np.pi * frequency_hz * times)


def _wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def test_canonicalization_decodes_stereo_44100_to_mono_22050() -> None:
    left = _sine(220.0, 0.5, sample_rate=44_100)
    right = _sine(440.0, 0.5, sample_rate=44_100)
    stereo = np.stack([left, right], axis=1)

    canonical = canonicalize_audio_bytes(_wav_bytes(stereo, 44_100), fmt="wav")

    assert canonical.ndim == 1
    assert len(canonical) == pytest.approx(CANONICAL_SAMPLE_RATE * 0.5, abs=2)
    assert np.isfinite(canonical).all()


def test_measured_series_preserve_expected_synthetic_directions() -> None:
    amplitude = np.concatenate([_sine(440.0, 1.0, amplitude=0.1), _sine(440.0, 1.0, amplitude=0.8)])
    features = extract_measured_perceptual_series(amplitude, CANONICAL_SAMPLE_RATE)
    rms = features["rms"]
    times = np.asarray(rms.frame_times_seconds)
    values = np.asarray(rms.values)
    quiet = float(np.median(values[(times >= 0.2) & (times <= 0.8)]))
    loud = float(np.median(values[(times >= 1.2) & (times <= 1.8)]))
    assert loud / quiet == pytest.approx(8.0, rel=0.03)

    frequency = np.concatenate([_sine(220.0, 1.0), _sine(4_000.0, 1.0)])
    features = extract_measured_perceptual_series(frequency, CANONICAL_SAMPLE_RATE)
    centroid = features["spectral_centroid"]
    times = np.asarray(centroid.frame_times_seconds)
    values = np.asarray(centroid.values)
    low = float(np.median(values[(times >= 0.2) & (times <= 0.8)]))
    high = float(np.median(values[(times >= 1.2) & (times <= 1.8)]))
    assert high > low * 10


def test_relative_band_energy_is_gain_invariant() -> None:
    source = _sine(100.0, 1.0)
    original = extract_measured_perceptual_series(source, CANONICAL_SAMPLE_RATE)[
        "relative_band_energy"
    ]
    quiet = extract_measured_perceptual_series(source * 0.2, CANONICAL_SAMPLE_RATE)[
        "relative_band_energy"
    ]

    np.testing.assert_allclose(original.values, quiet.values, atol=1e-5, rtol=1e-5)


def test_onset_strength_increases_for_denser_transients() -> None:
    audio = np.zeros(CANONICAL_SAMPLE_RATE * 4, dtype=np.float32)
    for seconds in np.arange(0.25, 2.0, 0.5):
        audio[int(seconds * CANONICAL_SAMPLE_RATE)] = 1.0
    for seconds in np.arange(2.05, 4.0, 0.125):
        audio[int(seconds * CANONICAL_SAMPLE_RATE)] = 1.0

    onset = extract_measured_perceptual_series(audio, CANONICAL_SAMPLE_RATE)["onset_strength"]
    times = np.asarray(onset.frame_times_seconds)
    values = np.asarray(onset.values)
    sparse = float(np.mean(values[(times >= 0.2) & (times <= 1.9)]))
    dense = float(np.mean(values[(times >= 2.1) & (times <= 3.9)]))
    assert dense > sparse * 2


def test_report_round_trip_preserves_timing_dimensions_and_provenance() -> None:
    source_version_id = uuid4()
    report = build_perceptual_evidence_report(
        _sine(440.0, 1.0),
        source_version_id=source_version_id,
    )
    restored = PerceptualEvidenceReport.model_validate_json(report.model_dump_json())

    assert restored == report
    assert restored.source_version_id == source_version_id
    assert restored.preprocessing_version == PREPROCESSING_VERSION
    assert set(restored.series) == {
        "rms",
        "spectral_centroid",
        "relative_band_energy",
        "onset_strength",
    }
    for series in restored.series.values():
        assert series.sample_rate == CANONICAL_SAMPLE_RATE
        assert series.channel_mode == "mono"
        assert series.source_version_id == source_version_id
        assert series.provenance.engine == "librosa"
        assert series.provenance.engine_version
        assert series.provenance.preprocessing_version == PREPROCESSING_VERSION
        assert len(series.frame_times_seconds) == len(series.values)
        assert np.all(np.diff(series.frame_times_seconds) >= 0)


def test_invalid_audio_withholds_instead_of_fabricating_series() -> None:
    with pytest.raises(ValueError, match="at least"):
        build_perceptual_evidence_report(
            np.zeros(100, dtype=np.float32),
            source_version_id=uuid4(),
        )
    invalid = np.zeros(CANONICAL_SAMPLE_RATE, dtype=np.float32)
    invalid[100] = np.nan
    with pytest.raises(ValueError, match="finite"):
        build_perceptual_evidence_report(invalid, source_version_id=uuid4())


class _FakeStorageBucket:
    def __init__(self, state: dict, bucket: str):
        self.state = state
        self.bucket = bucket

    def download(self, key: str) -> bytes:
        self.state["download"] = (self.bucket, key)
        return self.state["source_bytes"]

    def upload(self, key: str, data: bytes, options: dict) -> None:
        self.state["upload"] = (self.bucket, key, data, options)


class _FakeStorage:
    def __init__(self, state: dict):
        self.state = state

    def from_(self, bucket: str) -> _FakeStorageBucket:
        return _FakeStorageBucket(self.state, bucket)


class _FakeJobsTable:
    def __init__(self):
        self.payloads: list[dict] = []

    def update(self, payload: dict):
        self.payloads.append(payload)
        return self

    def eq(self, _column: str, _value: str):
        return self

    def execute(self):
        return SimpleNamespace(data=[{}])


class _FakeClient:
    def __init__(self, source_bytes: bytes):
        self.state = {"source_bytes": source_bytes}
        self.storage = _FakeStorage(self.state)
        self.jobs = _FakeJobsTable()

    def table(self, name: str):
        assert name == "jobs"
        return self.jobs


def test_worker_capability_persists_report_with_source_lineage_and_no_insight(monkeypatch) -> None:
    owner_id = "owner"
    work_id = uuid4()
    source_artifact = Artifact(
        work_id=work_id, kind=ArtifactKind.audio_original, mime_type="audio/wav"
    )
    source_version = Version(
        artifact_id=source_artifact.id,
        storage_key="source.wav",
        storage_bucket="artifacts",
        label="source.wav",
    )
    report = build_perceptual_evidence_report(
        _sine(440.0, 1.0),
        source_version_id=source_version.id,
    )
    output_artifact = Artifact(
        work_id=work_id,
        kind=ArtifactKind.analysis_report,
        mime_type="application/json",
    )
    created: dict[str, object] = {}

    class FakeVersionRepo:
        def __init__(self, _client):
            pass

        def get(self, version_id, requested_owner):
            assert version_id == source_version.id
            assert requested_owner == owner_id
            return source_version

        def create(self, version, requested_owner):
            assert requested_owner == owner_id
            created["version"] = version
            return version

    class FakeArtifactRepo:
        def __init__(self, _client):
            pass

        def get(self, artifact_id, requested_owner):
            assert artifact_id == source_artifact.id
            assert requested_owner == owner_id
            return source_artifact

        def create(self, artifact, requested_owner):
            assert requested_owner == owner_id
            assert artifact.kind == ArtifactKind.analysis_report
            created["artifact"] = artifact
            return output_artifact

    monkeypatch.setattr(perceptual_capability, "VersionRepo", FakeVersionRepo)
    monkeypatch.setattr(perceptual_capability, "ArtifactRepo", FakeArtifactRepo)
    monkeypatch.setattr(
        perceptual_capability,
        "extract_perceptual_evidence_from_bytes",
        lambda *_args, **_kwargs: report,
    )

    client = _FakeClient(_wav_bytes(_sine(440.0, 1.0), CANONICAL_SAMPLE_RATE))
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="perceptual_series", version="1.0"),
        input_version_ids=[source_version.id],
        created_by=owner_id,
    )

    output_ids = perceptual_capability.handle_perceptual_series(job, client)

    output_version = created["version"]
    assert output_ids == [str(output_version.id)]
    assert output_version.parent_version_id == source_version.id
    assert output_version.lineage == [source_version.id]
    assert output_version.metadata["source_version_id"] == str(source_version.id)
    assert output_version.metadata["semantic_insights_emitted"] is False
    uploaded = client.state["upload"]
    restored = PerceptualEvidenceReport.model_validate_json(uploaded[2])
    assert restored.source_version_id == source_version.id

"""
Capability adapters — wrap OSS music-processing libraries behind the domain
Capability contract.  Each handler is a callable ``f(job: Job, client) -> list[str]``
that can be registered with :class:`JobWorker`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import os
import tempfile
from uuid import UUID

import numpy as np

import analyze
import music_features
from domain.capability_policy import is_product_evidence
from domain.models import (
    Alignment,
    AlignmentKind,
    Artifact,
    ArtifactKind,
    Capability,
    Entity,
    EntityKind,
    Insight,
    Job,
    NoteEntity,
    Span,
    TimelineUnit,
    Version,
)
from domain.repositories import (
    AlignmentRepo,
    ArtifactRepo,
    EntityRepo,
    InsightRepo,
    VersionRepo,
)
from observability import get_tracer

logger = logging.getLogger("capabilities")
_tracer = get_tracer("listencloser-engine")

_STORAGE_BUCKET = "artifacts"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _ProgressTable:
    """Map child-capability progress into a parent workflow interval."""

    def __init__(self, table, base: float, scale: float):
        self._table = table
        self._base = base
        self._scale = scale

    def update(self, data: dict):
        mapped = dict(data)
        if "progress" in mapped:
            mapped["progress"] = self._base + self._scale * float(mapped["progress"])
        return self._table.update(mapped)


class _ProgressClient:
    """Delegate a Supabase client while remapping updates to the jobs table."""

    def __init__(self, client, base: float, scale: float):
        self._client = client
        self._base = base
        self._scale = scale

    @property
    def storage(self):
        return self._client.storage

    def table(self, name: str):
        table = self._client.table(name)
        if name == "jobs":
            return _ProgressTable(table, self._base, self._scale)
        return table


def _resolve_owner_id(client, workflow_id: UUID) -> str:
    """Walk workflow → project → owner_id."""
    wf = client.table("workflows").select("project_id").eq("id", str(workflow_id)).execute()
    if not wf.data:
        raise ValueError(f"workflow {workflow_id} not found")
    proj = client.table("projects").select("owner_id").eq("id", wf.data[0]["project_id"]).execute()
    if not proj.data:
        raise ValueError(f"project not found for workflow {workflow_id}")
    return proj.data[0]["owner_id"]


def _lookup_version(client, version_id: UUID) -> Version:
    """Load a Version row directly (no owner check — service-role client)."""
    result = client.table("artifact_versions").select("*").eq("id", str(version_id)).execute()
    if not result.data:
        raise ValueError(f"version {version_id} not found")
    return Version.model_validate(result.data[0])


def _artifact_kind_for_version(client, version_id: UUID) -> ArtifactKind:
    version = _lookup_version(client, version_id)
    result = client.table("artifacts").select("kind").eq("id", str(version.artifact_id)).execute()
    if not result.data:
        raise ValueError(f"artifact {version.artifact_id} not found")
    return ArtifactKind(result.data[0]["kind"])


def _resolve_work_id(client, version_id: UUID) -> UUID:
    """Find the ``work_id`` that owns a version."""
    version = _lookup_version(client, version_id)
    result = (
        client.table("artifacts").select("work_id").eq("id", str(version.artifact_id)).execute()
    )
    if not result.data:
        raise ValueError(f"artifact {version.artifact_id} not found")
    return UUID(result.data[0]["work_id"])


def _update_progress(client, job_id: UUID, progress: float, message: str = "") -> None:
    """Update a running job or stop at the next cooperative boundary."""
    clamped = max(0.0, min(1.0, float(progress)))
    try:
        result = (
            client.table("jobs")
            .update({"progress": clamped, "status_message": message})
            .eq("id", str(job_id))
            .eq("stage", "running")
            .execute()
        )
        if result.data == []:
            raise RuntimeError("job is no longer running")
    except Exception:
        logger.exception("update_progress_failed", extra={"job_id": str(job_id)})
        raise


def _upload_bytes(
    client,
    bucket: str,
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> None:
    client.storage.from_(bucket).upload(key, data, {"content-type": content_type})


def _job_storage_key(job: Job, filename: str) -> str:
    """Keep automatic retry attempts immutable and collision-free."""
    return f"jobs/{job.id}/attempt-{job.lifecycle.retry_count}/{filename}"


def _create_output_version(
    client,
    work_id: UUID,
    kind: ArtifactKind,
    storage_key: str,
    content: bytes,
    parent_version_id: UUID | None,
    job: Job,
    owner_id: str,
    mime_type: str = "application/octet-stream",
    label: str = "",
    metadata: dict | None = None,
) -> UUID:
    """Create an Artifact + Version row and return the version id."""
    artifact_repo = ArtifactRepo(client)
    version_repo = VersionRepo(client)

    artifact = artifact_repo.create(
        Artifact(work_id=work_id, kind=kind, mime_type=mime_type),
        owner_id,
    )
    version = version_repo.create(
        Version(
            artifact_id=artifact.id,
            parent_version_id=parent_version_id,
            lineage=[parent_version_id] if parent_version_id else [],
            storage_key=storage_key,
            storage_bucket=_STORAGE_BUCKET,
            byte_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            produced_by_job_id=job.id,
            created_by=owner_id,
            label=label,
            metadata=metadata or {},
        ),
        owner_id,
    )
    return version.id


def _create_insight(
    client,
    version_id: UUID,
    kind: str,
    claim: str,
    evidence: dict | None = None,
    span: Span | None = None,
    confidence: float | None = None,
    job: Job | None = None,
    owner_id: str = "",
    method: str | None = None,
    engine_provenance: dict | None = None,
) -> UUID:
    """Create an Insight row and return its id.

    ``method`` is the evidence provenance: ``"detected"`` (direct measurement),
    ``"inferred"`` (derived via a model), or ``"heuristic"`` (rule-based). A
    missing insight for a fact is its ``"unavailable"`` state.
    ``engine_provenance`` is the engine metadata (engine name, library version,
    parameters) recorded by the engine seam that produced the fact.
    """
    repo = InsightRepo(client)
    provenance: dict = (
        {
            "capability": job.capability.name,
            "capability_version": job.capability.version,
        }
        if job
        else {}
    )
    if method:
        provenance["method"] = method
    if engine_provenance:
        provenance["engine"] = engine_provenance
    insight = repo.create(
        Insight(
            version_id=version_id,
            kind=kind,
            claim=claim,
            span=span or Span(),
            evidence=evidence or {},
            confidence=confidence,
            produced_by_job_id=job.id if job else None,
            created_by=owner_id if owner_id else None,
            provenance=provenance,
        ),
        owner_id,
    )
    return insight.id


# ---------------------------------------------------------------------------
# Audio descriptor extraction (Essentia / librosa)
# ---------------------------------------------------------------------------

_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])  # type: ignore[arg-type]
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])  # type: ignore[arg-type]
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_ESSENTIA_UNSUPPORTED_OS = False


def _merge_adjacent_identical_chords(chords: list[dict]) -> list[dict]:
    """Merge consecutive identical chords into single spans.

    Two adjacent chords are merged if they have the same root and quality
    and their time ranges are contiguous (end of first == start of second
    within floating-point tolerance).

    The original temporal evidence is preserved in the merged span (start
    of first, end of last). This is deterministic and tested.
    """
    if not chords:
        return []

    merged: list[dict] = []
    current = dict(chords[0])  # copy to avoid mutating input

    for ch in chords[1:]:
        if (
            ch.get("root") == current.get("root")
            and ch.get("quality") == current.get("quality")
            and abs(ch.get("start", 0) - current.get("end", 0)) < 0.05
        ):
            # Extend current span
            current["end"] = ch.get("end", current.get("end"))
        else:
            merged.append(current)
            current = dict(ch)

    merged.append(current)
    return merged


def _extract_essentia(audio: np.ndarray, sr: float) -> dict | None:
    try:
        import essentia.standard as es
    except Exception:
        return None

    try:
        if _ESSENTIA_UNSUPPORTED_OS:
            return None
        audio_es = np.array(audio, dtype=np.float32)
        result: dict = {}

        bpm_extractor = es.RhythmExtractor2013(method="multifeature")
        bpm_val, _, _, _, _ = bpm_extractor(audio_es)
        result["bpm"] = round(float(bpm_val), 1)

        key_extractor = es.KeyExtractor()
        key_str, key_scale, key_strength = key_extractor(audio_es)
        tonic = "C"
        mode = "major"
        if key_str is not None:
            tonic = str(key_str)
        if key_scale is not None:
            mode = str(key_scale).lower()
        result["key"] = {
            "tonic": tonic,
            "mode": mode,
            "confidence": round(float(key_strength), 3) if key_strength else None,
        }

        loudness_extractor = es.LoudnessEBUR128()
        _, _, integrated, _ = loudness_extractor(audio_es)
        result["loudness"] = round(float(integrated), 1)

        centroid_extractor = es.Centroid()
        centroid_val = centroid_extractor(audio_es)
        result["spectral_centroid"] = round(float(centroid_val), 0)

        return result
    except Exception:
        logger.warning("essentia extraction failed, falling back to librosa")
        return None


def _extract_librosa(audio: np.ndarray, sr: float) -> dict:
    import librosa
    import numpy as np

    result: dict = {}

    try:
        tempo, _ = librosa.beat.beat_track(y=audio, sr=float(sr))
        if tempo is not None and float(tempo) > 0:
            result["bpm"] = round(float(tempo), 1)
    except Exception:
        logger.debug("librosa tempo extraction failed")

    try:
        y_harm = librosa.effects.harmonic(audio)
        chroma = librosa.feature.chroma_cqt(y=y_harm, sr=float(sr))
        chroma_mean = np.mean(chroma, axis=1)
        if chroma_mean.sum() > 0:
            chroma_mean = chroma_mean / chroma_mean.max()

        best_corr = -1.0
        best_tonic = "C"
        best_mode = "major"
        for shift in range(12):
            rolled = np.roll(chroma_mean, shift)
            corr_major = float(np.dot(rolled, _KS_MAJOR))
            corr_minor = float(np.dot(rolled, _KS_MINOR))
            if corr_major > best_corr:
                best_corr = corr_major
                best_tonic = _NOTES[shift]
                best_mode = "major"
            if corr_minor > best_corr:
                best_corr = corr_minor
                best_tonic = _NOTES[shift]
                best_mode = "minor"

        max_possible = float(np.dot(_KS_MAJOR, _KS_MAJOR))
        confidence = best_corr / max_possible if max_possible > 0 else 0.0
        result["key"] = {
            "tonic": best_tonic,
            "mode": best_mode,
            "confidence": round(min(max(confidence, 0.0), 1.0), 3),
        }
    except Exception:
        logger.debug("librosa key extraction failed")

    try:
        rms = librosa.feature.rms(y=audio)
        rms_db = 20 * np.log10(np.mean(rms) + 1e-10)
        loudness_lufs = round(float(rms_db - 18.0), 1)
        result["loudness"] = loudness_lufs
    except Exception:
        logger.debug("librosa loudness extraction failed")

    try:
        centroid = librosa.feature.spectral_centroid(y=audio, sr=float(sr))
        result["spectral_centroid"] = round(float(np.mean(centroid)), 0)
    except Exception:
        logger.debug("librosa spectral centroid extraction failed")

    return result


def _extract_audio_descriptors(audio: np.ndarray, sr: float) -> dict:
    """Extract BPM, key, loudness, and spectral centroid.

    Tries Essentia first for higher-quality results; falls back to
    librosa (already a project dependency) when Essentia is unavailable.
    """
    result = _extract_essentia(audio, sr)
    if result is not None:
        return result
    return _extract_librosa(audio, sr)


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


def download_version_bytes(version: Version, client) -> bytes:
    """Fetch raw bytes for a version from Supabase Storage."""
    return client.storage.from_(version.storage_bucket).download(version.storage_key)


def _cleanup_partial_job_outputs(client, job_ids: list[str]) -> None:
    """Remove incomplete output graphs before retrying a composite workflow."""
    if not job_ids:
        return
    result = (
        client.table("artifact_versions")
        .select("artifact_id,storage_bucket,storage_key")
        .in_("produced_by_job_id", job_ids)
        .execute()
    )
    rows = result.data or []
    for bucket in {row["storage_bucket"] for row in rows}:
        keys = [row["storage_key"] for row in rows if row["storage_bucket"] == bucket]
        if keys:
            client.storage.from_(bucket).remove(keys)
    artifact_ids = sorted({row["artifact_id"] for row in rows})
    if artifact_ids:
        # Artifact deletion cascades versions, note entities, and insights.
        client.table("artifacts").delete().in_("id", artifact_ids).execute()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_understand(job: Job, client) -> list[str]:
    """Run the complete durable audio-understanding workflow.

    A single queued job owns transcription, note persistence, harmonic analysis,
    and score generation. Closing the browser therefore cannot strand a workflow
    between stages.
    """
    cleanup_job_ids: list[str] = []
    if job.lifecycle.retry_count > 0:
        cleanup_job_ids.append(str(job.id))
    retry_of = job.provenance.get("retry_of_job_id")
    if retry_of:
        cleanup_job_ids.append(str(retry_of))
    _cleanup_partial_job_outputs(client, cleanup_job_ids)

    transcribe_client = _ProgressClient(client, 0.0, 0.65)
    output_ids = handle_transcribe(job, transcribe_client)

    midi_version_id = next(
        (
            UUID(version_id)
            for version_id in output_ids
            if _artifact_kind_for_version(client, UUID(version_id)) == ArtifactKind.midi_performance
        ),
        None,
    )
    if midi_version_id is None:
        raise ValueError("understand workflow produced no MIDI version")

    structure_job = job.model_copy(
        update={
            "capability": Capability(name="audio_structure", version="1.0"),
            "input_version_ids": [job.input_version_ids[0]],
        }
    )
    handle_audio_structure(structure_job, _ProgressClient(client, 0.65, 0.10))
    analyze_job = job.model_copy(
        update={
            "capability": Capability(name="analyze", version="1.0"),
            "input_version_ids": [midi_version_id, job.input_version_ids[0]],
        }
    )
    handle_analyze(analyze_job, _ProgressClient(client, 0.75, 0.15))
    score_job = job.model_copy(
        update={
            "capability": Capability(name="score", version="1.0"),
            "input_version_ids": [midi_version_id, job.input_version_ids[0]],
        }
    )
    score_ids = handle_score(score_job, _ProgressClient(client, 0.90, 0.10))
    return [*output_ids, *score_ids]


def handle_transcribe(job: Job, client) -> list[str]:
    """Transcribe audio → MIDI.  Produces ``midi_performance`` and
    ``audio_rendered`` (synthesised WAV) output versions."""
    if not job.input_version_ids:
        raise ValueError("transcribe requires at least one input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    _update_progress(client, job.id, 0.1, "looking up input version")

    input_version = _lookup_version(client, job.input_version_ids[0])
    work_id = _resolve_work_id(client, input_version.id)

    _update_progress(client, job.id, 0.2, "downloading audio")
    audio_bytes = download_version_bytes(input_version, client)

    onset_threshold = float(job.parameters.get("onset_threshold", 0.5))
    frame_threshold = float(job.parameters.get("frame_threshold", 0.3))
    fmt = job.parameters.get("fmt", "wav")
    engine_name = job.parameters.get("transcription_engine")
    profile = job.parameters.get("transcription_profile")

    _update_progress(client, job.id, 0.25, "preparing audio")
    audio_bytes = music_features.decode_audio_to_wav(audio_bytes, fmt=fmt)

    _update_progress(client, job.id, 0.3, "transcribing audio")
    with _tracer.start_as_current_span(
        "transcription",
        attributes={
            "engine": engine_name or "auto",
            "profile": profile or "auto",
            "onset_threshold": onset_threshold,
            "frame_threshold": frame_threshold,
        },
    ):
        engine = music_features.get_transcription_engine_for_job(
            name=engine_name,
            profile=profile,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
        )
        result = engine.transcribe(audio_bytes, fmt="wav")

    # Some transcription engines (e.g. Transkun) return note/MIDI data only and
    # no synthesized audio. A zero-byte WAV would surface as a broken
    # "Transcription" playback source in the transport, so synthesize a WAV
    # from the produced MIDI as a guaranteed-playable fallback.
    if not result.wav:
        result = dataclasses.replace(result, wav=music_features.midi_to_wav(result.midi))

    output_ids: list[str] = []

    _update_progress(client, job.id, 0.6, "storing MIDI output")
    midi_key = _job_storage_key(job, "transcribed.mid")
    _upload_bytes(client, _STORAGE_BUCKET, midi_key, result.midi, "audio/midi")
    midi_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.midi_performance,
        midi_key,
        result.midi,
        input_version.id,
        job,
        owner_id,
        mime_type="audio/midi",
        label="Transcription MIDI",
        metadata={
            "note_count": result.num_notes,
            "cleanup": result.cleanup_report,
            "representation": "performance_midi",
            "quality_notice": (
                "Conservatively filtered transcription; timing is preserved rather than quantized."
            ),
            "provenance": result.provenance.to_dict(),
            "transcription_profile": profile or "auto",
            "routing_reason": f"profile={profile or 'auto'} -> engine={result.provenance.engine}",
            "tempo_is_placeholder": result.tempo_is_placeholder,
            "meter_is_placeholder": result.meter_is_placeholder,
            "supports_meter": result.supports_meter,
        },
    )
    output_ids.append(str(midi_version_id))

    _update_progress(client, job.id, 0.7, "storing note entities")
    note_entities: list[Entity] = []
    for item in result.notes:
        start = float(item["start"])
        end = float(item["end"])
        note_entities.append(
            Entity(
                version_id=midi_version_id,
                kind=EntityKind.note,
                span=Span(start_seconds=start, end_seconds=end),
                note=NoteEntity(
                    pitch=int(item["pitch"]),
                    start_seconds=start,
                    end_seconds=end,
                    velocity=int(item.get("velocity", 64)),
                    amplitude=item.get("amplitude"),
                ),
                label=f"MIDI {int(item['pitch'])}",
            )
        )
    EntityRepo(client).create_many(note_entities, owner_id)

    _update_progress(client, job.id, 0.8, "storing rendered audio")
    wav_key = _job_storage_key(job, "transcribed.wav")
    _upload_bytes(client, _STORAGE_BUCKET, wav_key, result.wav, "audio/wav")
    audio_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.audio_rendered,
        wav_key,
        result.wav,
        input_version.id,
        job,
        owner_id,
        mime_type="audio/wav",
        label="Transcription playback",
    )
    output_ids.append(str(audio_version_id))

    _update_progress(client, job.id, 1.0, "transcription complete")
    return output_ids


def handle_audio_structure(job: Job, client) -> list[str]:
    """Persist original-audio tempo, meter anchors, and functional sections."""
    if not job.input_version_ids:
        raise ValueError("audio_structure requires an audio input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    input_version = _lookup_version(client, job.input_version_ids[0])
    _update_progress(client, job.id, 0.1, "preparing audio structure analysis")
    audio_bytes = download_version_bytes(input_version, client)
    wav_bytes = music_features.decode_audio_to_wav(
        audio_bytes, fmt=job.parameters.get("fmt", "wav")
    )
    _update_progress(client, job.id, 0.35, "finding beats and musical form")
    with _tracer.start_as_current_span("audio_structure"):
        result = music_features.structure_with_engine(wav_bytes)
    if result is not None:
        pass  # provenance captured via insight persistence below

    # The model remains optional until its heavyweight PyTorch/NATTEN runtime
    # is installed on the free ARM worker. Never fail an otherwise useful import
    # or invent structure when it is unavailable.
    if result is None:
        _update_progress(client, job.id, 1.0, "audio structure analysis unavailable")
        return []

    _update_progress(client, job.id, 0.65, "storing beat grid and sections")
    entities: list[Entity] = []
    for index, time in enumerate(result.downbeats[:1000]):
        entities.append(
            Entity(
                version_id=input_version.id,
                kind=EntityKind.beat,
                span=Span(start_seconds=time),
                label=f"Downbeat {index + 1}",
            )
        )
    for index, segment in enumerate(result.segments[:200]):
        entities.append(
            Entity(
                version_id=input_version.id,
                kind=EntityKind.section,
                span=Span(start_seconds=segment["start"], end_seconds=segment["end"]),
                label=f"{segment['label'].title()} {index + 1}",
            )
        )
    if entities:
        EntityRepo(client).create_many(entities, owner_id)

    insight_ids: list[str] = []
    insight_ids.append(
        str(
            _create_insight(
                client,
                input_version.id,
                "audio_structure",
                (
                    f"{len(result.segments)} labelled sections · "
                    f"{len(result.downbeats)} downbeats · {round(result.bpm)} BPM"
                ),
                evidence={
                    **result.evidence(),
                    "beats_seconds": result.beats,
                    "downbeats_seconds": result.downbeats,
                },
                confidence=None,
                job=job,
                owner_id=owner_id,
                method="inferred",
            )
        )
    )
    insight_ids.append(
        str(
            _create_insight(
                client,
                input_version.id,
                "audio_tempo",
                f"Recording tempo: {round(result.bpm)} BPM",
                evidence={"bpm": result.bpm, "source": "audio_structure"},
                confidence=None,
                job=job,
                owner_id=owner_id,
                method="detected",
            )
        )
    )
    for segment in result.segments[:100]:
        insight_ids.append(
            str(
                _create_insight(
                    client,
                    input_version.id,
                    "section",
                    segment["label"].title(),
                    evidence={
                        "label": segment["label"],
                        "start_seconds": segment["start"],
                        "end_seconds": segment["end"],
                        "engine": result.provenance.engine,
                        "model": result.provenance.model,
                    },
                    span=Span(start_seconds=segment["start"], end_seconds=segment["end"]),
                    confidence=None,
                    job=job,
                    owner_id=owner_id,
                    method="inferred",
                )
            )
        )
    _update_progress(client, job.id, 1.0, "audio structure analysis complete")
    return insight_ids


def _transcription_defaults_pulse(input_version: Version) -> bool:
    """True when a MIDI's tempo/meter are transcription defaults, not evidence.

    Engines declare whether their transcription output carries placeholder
    tempo/meter (e.g. basic_pitch's 120 BPM and 4/4) through explicit metadata
    flags on the output version, never via engine-name matching.
    """
    metadata = input_version.metadata or {}
    if not isinstance(metadata, dict):
        return False
    return bool(metadata.get("tempo_is_placeholder") or metadata.get("meter_is_placeholder"))


def handle_analyze(job: Job, client) -> list[str]:
    """Analyze MIDI → insights for key, tempo, time signature, chords,
    Roman numerals, and cadences.

    When the job carries a second input version (the original audio, as wired
    by ``handle_understand``), real pulse evidence (BPM, beats, downbeats) is
    measured from that audio and threaded into the analysis so tempo/meter/rhythm
    reflect the recording rather than transcription placeholders.
    """
    if not job.input_version_ids:
        raise ValueError("analyze requires at least one input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    _update_progress(client, job.id, 0.1, "looking up input MIDI")

    input_version = _lookup_version(client, job.input_version_ids[0])

    _update_progress(client, job.id, 0.2, "downloading MIDI")
    midi_bytes = download_version_bytes(input_version, client)

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        f.write(midi_bytes)
        midi_path = f.name

    pulse: dict | None = None
    wav_bytes: bytes | None = None
    if len(job.input_version_ids) > 1:
        try:
            _update_progress(client, job.id, 0.25, "measuring audio pulse")
            audio_version = _lookup_version(client, job.input_version_ids[1])
            audio_bytes = download_version_bytes(audio_version, client)
            wav_bytes = music_features.decode_audio_to_wav(
                audio_bytes, fmt=job.parameters.get("fmt", "wav")
            )
            with _tracer.start_as_current_span(
                "beat_analysis",
                attributes={"engine": "beat_this"},
            ):
                beat_result = music_features.estimate_beats_with_engine(
                    wav_bytes, engine_name="beat_this"
                )
            pulse = {
                "bpm": beat_result.get("bpm"),
                "beats": beat_result.get("beats") or [],
                "downbeats": beat_result.get("downbeats"),
                "provenance": beat_result.get("provenance"),
            }
        except Exception:
            logger.exception("analyze_pulse_measurement_failed")

    _update_progress(client, job.id, 0.3, "running analysis")
    with _tracer.start_as_current_span("music_analysis"):
        try:
            analysis = analyze.analyze_midi(midi_path, pulse=pulse, audio_bytes=wav_bytes)
        finally:
            os.unlink(midi_path)

    insight_ids: list[str] = []
    pulse_is_default = _transcription_defaults_pulse(input_version)
    harmony_provenance = analysis.get("harmony_provenance") or {}
    melody_provenance = analysis.get("melody_provenance")

    def _hp(component: str) -> dict | None:
        """Per-component harmony provenance (None when unavailable)."""
        return harmony_provenance.get(component)

    # Key — only written when there is a real detection with a correlation
    # coefficient. A weak correlation is still stored (the frontend withholds
    # it from the primary summary), but a failed detection is not fabricated.
    _update_progress(client, job.id, 0.45, "storing key insight")
    key_data = analysis.get("key") or {}
    key_conf = float(key_data.get("confidence", 0.0))
    key_source = analysis.get("key_source", "harmony_engine")
    key_provenance = analysis.get("key_provenance")
    if key_data:
        tonic = key_data.get("tonic", "?")
        mode = key_data.get("mode", "?")
        kid = _create_insight(
            client,
            input_version.id,
            "key",
            f"Key: {tonic} {mode}",
            evidence={
                "tonic": tonic,
                "mode": mode,
                "key_source": key_source,
                "key_provenance": key_provenance,
            },
            confidence=key_conf,
            job=job,
            owner_id=owner_id,
            method="detected",
            engine_provenance=_hp("key"),
        )
        insight_ids.append(str(kid))

    # Tempo — the transcribed MIDI carries basic_pitch's 120 BPM default, not
    # audio/beat evidence, so without real pulse evidence it is not surfaced as
    # a detected fact. When the audio beat tracker supplies measured BPM, that
    # evidence overrides the placeholder. A degenerate beat estimate produces no
    # tempo fact at all (never a fabricated 120).
    _update_progress(client, job.id, 0.50, "storing tempo insight")
    tempo_data = analysis.get("tempo") or {}
    pulse_provenance = analysis.get("pulse_provenance") or {}
    tempo_is_measured = tempo_data.get("source") == "audio_beat_tracking"
    if tempo_data and (not pulse_is_default or tempo_is_measured):
        bpm = float(tempo_data.get("bpm", 0))
        tempo_conf = tempo_data.get("confidence")
        tempo_conf = float(tempo_conf) if tempo_conf is not None else None
        tid = _create_insight(
            client,
            input_version.id,
            "tempo",
            f"Tempo: {bpm} BPM",
            evidence={"bpm": bpm, "source": tempo_data.get("source", "midi_metadata")},
            confidence=tempo_conf,
            job=job,
            owner_id=owner_id,
            method="detected",
            engine_provenance=pulse_provenance or None,
        )
        insight_ids.append(str(tid))

    # Time signature — never inferred from beat/downbeat timestamps. A beat
    # model gives temporal pulse and bar starts, not the notated beat unit, so
    # the audio path leaves meter unknown (never a fabricated 4/4). Only a real
    # MIDI file's explicit metadata meter (no audio pulse) is surfaced, and
    # handle_analyze still suppresses the basic_pitch 4/4 placeholder.
    _update_progress(client, job.id, 0.55, "storing time signature insight")
    ts_data = analysis.get("time_signature") or {}
    ts_is_measured = ts_data.get("source") == "audio_beat_tracking"
    if ts_data and (not pulse_is_default or ts_is_measured):
        num = int(ts_data.get("numerator", 4))
        den = int(ts_data.get("denominator", 4))
        ts_conf = ts_data.get("confidence")
        ts_conf = float(ts_conf) if ts_conf is not None else None
        tsid = _create_insight(
            client,
            input_version.id,
            "time_signature",
            f"Time Signature: {num}/{den}",
            evidence={
                "numerator": num,
                "denominator": den,
                "source": ts_data.get("source", "midi_metadata"),
            },
            confidence=ts_conf,
            job=job,
            owner_id=owner_id,
            method="detected",
            engine_provenance=pulse_provenance or None,
        )
        insight_ids.append(str(tsid))

    # Chords — engine-gated persistence.
    # music21 symbolic chord detection (root=0.02) is unreliable and withheld.
    # lv-chordia audio-native detection (root=0.787 on GuitarSet comp) is
    # the trusted chord source. Only persist chords when provenance confirms
    # they came from a validated engine.
    chords = analysis.get("chords", []) or []
    chord_provenance = _hp("chords")
    chord_engine = chord_provenance.get("engine") if chord_provenance else None
    chord_engine_trusted = chord_engine == "lv-chordia"

    if chord_engine_trusted and chords:
        # Filter out N (no-chord) markers — these represent gaps, not chords
        harmonic_chords = [c for c in chords if c.get("root") != "N"]

        # Collapse consecutive identical chords into merged spans
        merged_chords = _merge_adjacent_identical_chords(harmonic_chords)

        # Persist as chord insights (max 20 to avoid overwhelming the UI)
        for ch in merged_chords[:20]:
            root = ch.get("root", "?")
            quality = ch.get("quality", "")
            label = f"{root} {quality}".strip()
            ch_start = ch.get("start")
            ch_end = ch.get("end")
            cid = _create_insight(
                client,
                input_version.id,
                "chord",
                label,
                evidence={
                    "root": root,
                    "quality": quality,
                    "start_seconds": ch_start,
                    "end_seconds": ch_end,
                },
                span=Span(
                    start_seconds=ch_start,
                    end_seconds=ch_end,
                ),
                confidence=None,
                job=job,
                owner_id=owner_id,
                method="detected",
                engine_provenance=chord_provenance,
            )
            insight_ids.append(str(cid))

        logger.info(
            "chords_persisted",
            extra={
                "raw_count": len(chords),
                "harmonic_count": len(harmonic_chords),
                "merged_count": len(merged_chords),
                "persisted_count": min(len(merged_chords), 20),
                "engine": chord_engine,
            },
        )
    else:
        # Chords not from a trusted engine — withhold
        logger.info(
            "chords_withheld",
            extra={
                "count": len(chords),
                "engine": chord_engine,
                "reason": "untrusted_engine" if chords else "no_chords",
            },
        )

    # Roman numerals — WITHHELD until independently verified against lv-chordia stream
    rns = analysis.get("roman_numerals", []) or []
    if rns:
        logger.info(
            "roman_numerals_withheld",
            extra={"count": len(rns), "reason": "pending_independent_verification"},
        )

    # Theory-derived Roman numerals (from TheoryInterpreter, not music21)
    # These are persisted when chord engine is lv-chordia AND trusted key exists
    rns_theory = analysis.get("roman_numerals_theory", []) or []
    theory_provenance = analysis.get("theory_provenance")
    if chord_engine_trusted and rns_theory:
        # Persist as RN insights (max 30 to avoid overwhelming the UI)
        for rn in rns_theory[:30]:
            numeral = rn.get("numeral", "")
            if not numeral:
                continue
            key_ctx = rn.get("key_context", "")
            rn_key_source = rn.get("key_source")
            rn_key_prov = rn.get("key_provenance")
            label = f"{numeral} ({key_ctx})" if key_ctx else numeral
            rn_start = rn.get("start")
            rn_end = rn.get("end")
            rnid = _create_insight(
                client,
                input_version.id,
                "roman_numeral",
                label,
                evidence={
                    "numeral": numeral,
                    "degree": rn.get("degree"),
                    "quality": rn.get("quality"),
                    "inversion": rn.get("inversion"),
                    "is_secondary": rn.get("is_secondary"),
                    "secondary_target": rn.get("secondary_target"),
                    "start_seconds": rn_start,
                    "end_seconds": rn_end,
                    "key_context": key_ctx,
                    "key_source": rn_key_source,
                    "key_provenance": rn_key_prov,
                },
                span=Span(
                    start_seconds=rn_start,
                    end_seconds=rn_end,
                ),
                confidence=None,
                job=job,
                owner_id=owner_id,
                method="inferred",
                engine_provenance=theory_provenance,
            )
            insight_ids.append(str(rnid))

        logger.info(
            "roman_numerals_persisted",
            extra={
                "count": len(rns_theory),
                "persisted_count": min(len(rns_theory), 30),
                "engine": "theory_interpreter",
            },
        )
    else:
        logger.info(
            "roman_numerals_withheld",
            extra={"count": len(rns_theory), "reason": "no_trusted_chords"},
        )

    # Harmonic functions (from TheoryInterpreter)
    functions = analysis.get("harmonic_functions", []) or []
    if chord_engine_trusted and functions:
        # Persist as function insights (max 30)
        for func in functions[:30]:
            function_name = func.get("function", "")
            numeral = func.get("numeral", "")
            if not function_name or function_name == "AMBIGUOUS":
                continue
            func_key_source = func.get("key_source")
            func_key_prov = func.get("key_provenance")
            label = f"{function_name} ({numeral})"
            func_start = func.get("start")
            func_end = func.get("end")
            fid = _create_insight(
                client,
                input_version.id,
                "harmonic_function",
                label,
                evidence={
                    "function": function_name,
                    "numeral": numeral,
                    "start_seconds": func_start,
                    "end_seconds": func_end,
                    "key_context": func.get("key_context"),
                    "key_source": func_key_source,
                    "key_provenance": func_key_prov,
                },
                span=Span(
                    start_seconds=func_start,
                    end_seconds=func_end,
                ),
                confidence=None,
                job=job,
                owner_id=owner_id,
                method="inferred",
                engine_provenance=theory_provenance,
            )
            insight_ids.append(str(fid))

        logger.info(
            "harmonic_functions_persisted",
            extra={
                "count": len(functions),
                "persisted_count": min(len(functions), 30),
                "engine": "theory_interpreter",
            },
        )
    else:
        logger.info(
            "harmonic_functions_withheld",
            extra={"count": len(functions), "reason": "no_trusted_chords"},
        )

    # Cadences — policy-gated: withheld until cadence detection is validated.
    cadences_theory = analysis.get("cadences_theory", []) or []
    if cadences_theory and not is_product_evidence("cadence"):
        logger.info(
            "cadences_withheld",
            extra={
                "count": len(cadences_theory),
                "reason": "capability_policy_withheld",
            },
        )

    # Key regions — policy-gated: withheld until a real modulation detector is validated.
    key_regions = analysis.get("key_regions_theory", []) or []
    if key_regions and not is_product_evidence("key_region"):
        logger.info(
            "key_regions_withheld",
            extra={
                "count": len(key_regions),
                "reason": "capability_policy_withheld",
            },
        )

    # Rhythm: compact, evidence-backed observations instead of a wall of cards.
    rhythm = analysis.get("rhythm") or {}
    if rhythm:
        offbeat_ratio = rhythm.get("offbeat_onset_ratio")
        if offbeat_ratio is not None:
            claim = (
                f"{rhythm.get('rhythmic_density', 0)} notes/sec · "
                f"{round(float(offbeat_ratio) * 100)}% note onsets off the detected beat grid"
            )
        else:
            claim = (
                f"{rhythm.get('rhythmic_density', 0)} notes/sec · "
                "off-beat fraction unavailable (no beat grid)"
            )
        rid = _create_insight(
            client,
            input_version.id,
            "rhythm",
            claim,
            evidence=rhythm,
            confidence=None,
            job=job,
            owner_id=owner_id,
            method="heuristic",
            engine_provenance=pulse_provenance or None,
        )
        insight_ids.append(str(rid))

        # Temporal rhythm features (Analysis V2): note density over time
        note_density = rhythm.get("note_density_over_time") or []
        if note_density:
            ndid = _create_insight(
                client,
                input_version.id,
                "rhythm_density",
                f"Note density profile: {len(note_density)} windows",
                evidence={
                    "windows": note_density,
                    "coverage": {
                        "policy_version": "complete_series_v1",
                        "total_generated_window_count": len(note_density),
                        "stored_window_count": len(note_density),
                        "start_seconds": note_density[0].get("start"),
                        "end_seconds": note_density[-1].get("end"),
                        "truncated": False,
                    },
                },
                confidence=None,
                job=job,
                owner_id=owner_id,
                method="computed",
                engine_provenance=pulse_provenance or None,
            )
            insight_ids.append(str(ndid))

        # Rest segments
        rests = rhythm.get("rest_segments") or []
        if rests:
            rsid = _create_insight(
                client,
                input_version.id,
                "rhythm_rests",
                f"{len(rests)} rest segment(s) detected",
                evidence={"rests": rests[:20]},
                confidence=None,
                job=job,
                owner_id=owner_id,
                method="computed",
                engine_provenance=pulse_provenance or None,
            )
            insight_ids.append(str(rsid))

    # Harmonic rhythm — policy-gated: withheld (depends on unreliable chord stream)
    harmonic_rhythm = analysis.get("harmonic_rhythm") or []
    if harmonic_rhythm and not is_product_evidence("harmonic_rhythm"):
        logger.info(
            "harmonic_rhythm_withheld",
            extra={"count": len(harmonic_rhythm), "reason": "capability_policy_withheld"},
        )

    melody = analysis.get("melody") or {}
    if melody:
        # quality_score is a note-fraction confidence proxy from LStoM,
        # not a calibrated probability; preserved in evidence only.
        mid = _create_insight(
            client,
            input_version.id,
            "melody",
            f"Range: MIDI {melody.get('low_pitch')}–{melody.get('high_pitch')} · "
            f"{round(float(melody.get('stepwise_ratio', 0)) * 100)}% "
            "stepwise motion",
            evidence=melody,
            confidence=None,
            job=job,
            owner_id=owner_id,
            method=melody.get("heuristic", "lstom_biLSTM"),
            engine_provenance=melody_provenance,
        )
        insight_ids.append(str(mid))

        # Melody interpretation findings (temporal events)
        melody_findings = analysis.get("melody_findings") or []
        for finding in melody_findings[:15]:  # Cap at 15 findings
            kind = finding.get("kind", "")
            claim = finding.get("claim", "")
            start = finding.get("start_seconds")
            end = finding.get("end_seconds")
            evidence = finding.get("evidence", {})

            # Add note_ids to evidence for frontend annotation linking
            if finding.get("note_ids"):
                evidence["note_ids"] = finding["note_ids"]

            fid = _create_insight(
                client,
                input_version.id,
                kind,
                claim,
                evidence=evidence,
                span=Span(start_seconds=start, end_seconds=end) if start is not None else None,
                confidence=None,
                job=job,
                owner_id=owner_id,
                method="lstom_interpretation",
                engine_provenance=melody_provenance,
            )
            insight_ids.append(str(fid))

        if melody_findings:
            logger.info(
                "melody_findings_persisted",
                extra={"count": len(melody_findings), "persisted": min(len(melody_findings), 15)},
            )

        # Motif findings (repeated melodic fragments)
        melody_motifs = analysis.get("melody_motifs") or []
        for motif in melody_motifs[:5]:  # Cap at 5 motifs
            claim = motif.get("claim", "")
            occurrences = motif.get("occurrences", [])

            if len(occurrences) < 2:
                continue

            # Use the first occurrence's span for the insight
            first = occurrences[0]
            last = occurrences[-1]

            mid2 = _create_insight(
                client,
                input_version.id,
                "melody_motif",
                claim,
                evidence={
                    "interval_pattern": motif.get("interval_pattern", []),
                    "length": motif.get("length"),
                    "count": motif.get("count"),
                    "occurrences": occurrences,
                },
                span=Span(
                    start_seconds=first.get("start_seconds"),
                    end_seconds=last.get("end_seconds"),
                ),
                confidence=None,
                job=job,
                owner_id=owner_id,
                method="interval_sequence_matching",
                engine_provenance=melody_provenance,
            )
            insight_ids.append(str(mid2))

        if melody_motifs:
            logger.info(
                "melody_motifs_persisted",
                extra={"count": len(melody_motifs), "persisted": min(len(melody_motifs), 5)},
            )

    # Voice leading — policy-gated: withheld (depends on unreliable chord stream)
    voice_leading = analysis.get("voice_leading") or {}
    if voice_leading and not is_product_evidence("voice_leading"):
        logger.info(
            "voice_leading_withheld",
            extra={"reason": "capability_policy_withheld"},
        )

    _update_progress(client, job.id, 1.0, f"analysis complete ({len(insight_ids)} insights)")
    # Insights are queried by input version. Job outputs only contain artifact
    # version IDs, so do not mix insight IDs into that contract.
    return []


def handle_score(job: Job, client) -> list[str]:
    """Create beat-aligned notation MIDI and MusicXML from a performance MIDI."""
    if not job.input_version_ids:
        raise ValueError("score requires a MIDI input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    input_version = _lookup_version(client, job.input_version_ids[0])
    work_id = _resolve_work_id(client, input_version.id)
    _update_progress(client, job.id, 0.2, "downloading MIDI")
    midi_bytes = download_version_bytes(input_version, client)
    beat_times: list[float] = []
    tempo = 0.0
    if len(job.input_version_ids) > 1:
        try:
            _update_progress(client, job.id, 0.35, "aligning notation to the recording")
            audio_bytes = download_version_bytes(
                _lookup_version(client, job.input_version_ids[1]), client
            )
            wav_bytes = music_features.decode_audio_to_wav(
                audio_bytes, fmt=job.parameters.get("fmt", "wav")
            )
            beat_result = music_features.estimate_beats_with_engine(wav_bytes)
            tempo = beat_result["bpm"]
            beat_times = beat_result["beats"]
            downbeats = beat_result.get("downbeats")
        except Exception:
            logger.exception("score_beat_tracking_failed")
    _update_progress(client, job.id, 0.5, "creating notation")
    with _tracer.start_as_current_span("notation"):
        notation_result = music_features.notation_with_engine(
            midi_bytes,
            beat_times,
            downbeats=downbeats,
            adaptive=True,
            notation_ready=True,
            piano_grand_staff=True,
        )
    notation_midi = notation_result["notation_midi"]
    notation_report = notation_result["quantization_report"]
    notation_key = _job_storage_key(job, "notation.mid")
    _upload_bytes(client, _STORAGE_BUCKET, notation_key, notation_midi, "audio/midi")
    notation_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.midi_corrected,
        notation_key,
        notation_midi,
        input_version.id,
        job,
        owner_id,
        mime_type="audio/midi",
        label="Beat-aligned notation MIDI",
        metadata={
            "notation": notation_report,
            "estimated_tempo_bpm": tempo,
            "beat_provenance": beat_result.get("provenance"),
        },
    )
    musicxml = notation_result["musicxml"]
    storage_key = _job_storage_key(job, "score.musicxml")
    _upload_bytes(
        client,
        _STORAGE_BUCKET,
        storage_key,
        musicxml,
        "application/vnd.recordare.musicxml+xml",
    )
    version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.musicxml_score,
        storage_key,
        musicxml,
        notation_version_id,
        job,
        owner_id,
        mime_type="application/vnd.recordare.musicxml+xml",
        label="Quantized notation draft",
        metadata={
            "representation": "notation_draft",
            "notation_midi_version_id": str(notation_version_id),
            "notation": notation_report,
            "quality_notice": "Derived from automatic transcription; review by ear before sharing.",
        },
    )

    # Score playback is derived from the notation representation (quantized
    # notation MIDI), never the raw performance MIDI. A separate synthesized
    # artifact keeps the three playback sources semantically distinct.
    score_audio_version_id: UUID | None = None
    _update_progress(client, job.id, 0.95, "rendering score playback")
    try:
        score_audio = music_features.midi_to_wav(notation_midi)
        measure_starts = music_features.measure_start_seconds(notation_midi)
    except Exception:
        logger.exception("score_playback_render_failed")
        score_audio = None
        measure_starts = []
    if score_audio is not None:
        score_key = _job_storage_key(job, "score.wav")
        _upload_bytes(client, _STORAGE_BUCKET, score_key, score_audio, "audio/wav")
        score_audio_version_id = _create_output_version(
            client,
            work_id,
            ArtifactKind.rendered_score,
            score_key,
            score_audio,
            notation_version_id,
            job,
            owner_id,
            mime_type="audio/wav",
            label="Score playback",
            metadata={
                "representation": "score_playback",
                "measure_starts_seconds": measure_starts,
                "notation_midi_version_id": str(notation_version_id),
                "quality_notice": (
                    "Synthesized from the quantized notation, not the raw performance."
                ),
            },
        )
    _update_progress(client, job.id, 1.0, "score complete")
    output_ids = [str(notation_version_id), str(version_id)]
    if score_audio_version_id is not None:
        output_ids.append(str(score_audio_version_id))
    return output_ids


def handle_enhance(job: Job, client) -> list[str]:
    """Enhance audio (denoise, declip, EBU R128 normalize)."""
    if not job.input_version_ids:
        raise ValueError("enhance requires at least one input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    _update_progress(client, job.id, 0.1, "looking up input version")

    input_version = _lookup_version(client, job.input_version_ids[0])
    work_id = _resolve_work_id(client, input_version.id)

    _update_progress(client, job.id, 0.3, "downloading audio")
    audio_bytes = download_version_bytes(input_version, client)

    fmt = job.parameters.get("fmt", "wav")

    _update_progress(client, job.id, 0.5, "enhancing audio")
    enhanced = music_features.enhance_audio(audio_bytes, fmt=fmt)

    _update_progress(client, job.id, 0.7, "storing enhanced audio")
    storage_key = _job_storage_key(job, "enhanced.wav")
    _upload_bytes(client, _STORAGE_BUCKET, storage_key, enhanced, "audio/wav")

    enhanced_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.audio_enhanced,
        storage_key,
        enhanced,
        input_version.id,
        job,
        owner_id,
        mime_type="audio/wav",
    )

    _update_progress(client, job.id, 1.0, "enhancement complete")
    return [str(enhanced_version_id)]


def handle_synthesize(job: Job, client) -> list[str]:
    """Synthesize MIDI → WAV audio via FluidSynth (or numpy fallback)."""
    if not job.input_version_ids:
        raise ValueError("synthesize requires at least one input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    _update_progress(client, job.id, 0.1, "looking up input MIDI")

    input_version = _lookup_version(client, job.input_version_ids[0])
    work_id = _resolve_work_id(client, input_version.id)

    _update_progress(client, job.id, 0.3, "downloading MIDI")
    midi_bytes = download_version_bytes(input_version, client)

    sr = int(job.parameters.get("sample_rate", 22050))

    _update_progress(client, job.id, 0.5, "synthesising audio")
    wav_bytes = music_features.midi_to_wav(midi_bytes, sr=sr)

    _update_progress(client, job.id, 0.7, "storing synthesised audio")
    storage_key = _job_storage_key(job, "synthesised.wav")
    _upload_bytes(client, _STORAGE_BUCKET, storage_key, wav_bytes, "audio/wav")

    audio_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.audio_rendered,
        storage_key,
        wav_bytes,
        input_version.id,
        job,
        owner_id,
        mime_type="audio/wav",
        label=str(job.parameters.get("label", "Synthesised playback")),
    )

    _update_progress(client, job.id, 1.0, "synthesis complete")
    return [str(audio_version_id)]


def handle_correct(job: Job, client) -> list[str]:
    """Replace notes in a selected region of a MIDI file with corrected notes."""
    import io

    import pretty_midi

    if not job.input_version_ids:
        raise ValueError("correct requires at least one input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    _update_progress(client, job.id, 0.1, "looking up input MIDI")

    input_version = _lookup_version(client, job.input_version_ids[0])
    work_id = _resolve_work_id(client, input_version.id)

    _update_progress(client, job.id, 0.2, "downloading MIDI")
    midi_bytes = download_version_bytes(input_version, client)

    _update_progress(client, job.id, 0.3, "loading MIDI")
    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))

    corrected_notes = job.parameters.get("corrected_notes", [])
    selection_start = job.parameters.get("selection_start")
    selection_end = job.parameters.get("selection_end")

    _update_progress(client, job.id, 0.5, "replacing notes")

    if selection_start is not None and selection_end is not None:
        for instrument in pm.instruments:
            instrument.notes = [
                n
                for n in instrument.notes
                if not (n.start >= selection_start and n.end <= selection_end)
            ]

    if pm.instruments:
        instrument = pm.instruments[0]
    else:
        instrument = pretty_midi.Instrument(program=0, is_drum=False, name="Corrected")
        pm.instruments.append(instrument)

    for cn in corrected_notes:
        pitch = int(cn["pitch"])
        start = float(cn["start"])
        end = float(cn["end"])
        velocity = int(cn.get("velocity", 64))
        instrument.notes.append(
            pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=end)
        )

    _update_progress(client, job.id, 0.7, "writing corrected MIDI")
    buf = io.BytesIO()
    pm.write(buf)
    corrected_bytes = buf.getvalue()

    _update_progress(client, job.id, 0.8, "storing corrected MIDI")
    storage_key = _job_storage_key(job, "corrected.mid")
    _upload_bytes(client, _STORAGE_BUCKET, storage_key, corrected_bytes, "audio/midi")

    output_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.midi_corrected,
        storage_key,
        corrected_bytes,
        input_version.id,
        job,
        owner_id,
        mime_type="audio/midi",
    )

    _update_progress(client, job.id, 0.9, "creating entity records")
    entity_repo = EntityRepo(client)
    for cn in corrected_notes:
        pitch = int(cn["pitch"])
        start = float(cn["start"])
        end = float(cn["end"])
        velocity = int(cn.get("velocity", 64))
        entity_repo.create(
            Entity(
                version_id=output_version_id,
                kind=EntityKind.note,
                span=Span(start_seconds=start, end_seconds=end),
                note=NoteEntity(
                    pitch=pitch,
                    start_seconds=start,
                    end_seconds=end,
                    velocity=velocity,
                ),
            ),
            owner_id,
        )

    _update_progress(client, job.id, 1.0, "correction complete")
    return [str(output_version_id)]


def handle_compare(job: Job, client) -> list[str]:
    """Compare note entities from two input versions.
    Produces an Alignment and an Insight with diff statistics."""
    if len(job.input_version_ids) < 2:
        raise ValueError("compare requires at least two input versions")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    _update_progress(client, job.id, 0.1, "fetching entities from version A")

    version_id_a = job.input_version_ids[0]
    version_id_b = job.input_version_ids[1]

    def _fetch_notes(version_id: UUID) -> list[dict]:
        result = (
            client.table("entities")
            .select("*")
            .eq("version_id", str(version_id))
            .eq("kind", "note")
            .execute()
        )
        notes: list[dict] = []
        for row in result.data:
            if row.get("note_pitch") is not None:
                notes.append(
                    {
                        "pitch": row["note_pitch"],
                        "start": float(row["note_start_seconds"]),
                        "end": float(row["note_end_seconds"]),
                        "velocity": row.get("note_velocity", 64),
                    }
                )
        return notes

    notes_a = _fetch_notes(version_id_a)
    notes_b = _fetch_notes(version_id_b)

    _update_progress(client, job.id, 0.3, "computing diff")

    notes_a.sort(key=lambda n: (n["pitch"], n["start"]))
    notes_b.sort(key=lambda n: (n["pitch"], n["start"]))

    EPS = 0.05
    used_b: set[int] = set()
    removed: list[dict] = []
    modified: list[dict] = []
    unchanged_count = 0

    for na in notes_a:
        matched = False
        for bi, nb in enumerate(notes_b):
            if bi in used_b:
                continue
            if na["pitch"] == nb["pitch"] and abs(na["start"] - nb["start"]) < EPS:
                matched = True
                used_b.add(bi)
                if abs(na["end"] - nb["end"]) >= EPS:
                    modified.append(
                        {
                            "pitch": na["pitch"],
                            "start_a": na["start"],
                            "end_a": na["end"],
                            "start_b": nb["start"],
                            "end_b": nb["end"],
                        }
                    )
                else:
                    unchanged_count += 1
                break
        if not matched:
            removed.append(na)

    added: list[dict] = []
    for bi, nb in enumerate(notes_b):
        if bi not in used_b:
            added.append(nb)

    _update_progress(client, job.id, 0.5, "creating alignment record")

    alignment_repo = AlignmentRepo(client)
    alignment = alignment_repo.create(
        Alignment(
            version_id=version_id_a,
            target_version_id=version_id_b,
            kind=AlignmentKind.version,
            source_unit=TimelineUnit.seconds,
            target_unit=TimelineUnit.seconds,
            mapping_data={
                "added_count": len(added),
                "removed_count": len(removed),
                "modified_count": len(modified),
                "unchanged_count": unchanged_count,
                "version_a_note_count": len(notes_a),
                "version_b_note_count": len(notes_b),
            },
            confidence=None,
            produced_by_job_id=job.id,
        ),
        owner_id,
    )

    _update_progress(client, job.id, 0.7, "creating insight record")

    insight_repo = InsightRepo(client)
    insight = insight_repo.create(
        Insight(
            version_id=version_id_a,
            kind="compare",
            claim=f"Comparison: {len(added)} added, {len(removed)} removed, "
            f"{len(modified)} modified, {unchanged_count} unchanged",
            evidence={
                "added_count": len(added),
                "removed_count": len(removed),
                "modified_count": len(modified),
                "unchanged_count": unchanged_count,
                "version_id_a": str(version_id_a),
                "version_id_b": str(version_id_b),
                "diff": {
                    "added": added,
                    "removed": removed,
                    "modified": modified,
                },
            },
            confidence=None,
            produced_by_job_id=job.id,
            provenance={
                "capability": job.capability.name,
                "capability_version": job.capability.version,
            },
        ),
        owner_id,
    )

    _update_progress(client, job.id, 1.0, "comparison complete")
    return [str(alignment.id), str(insight.id)]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def handle_transform(job: Job, client) -> list[str]:
    """Transform MIDI: transpose notes up/down by semitones."""
    import io

    import pretty_midi

    if not job.input_version_ids:
        raise ValueError("transform requires at least one input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    _update_progress(client, job.id, 0.1, "looking up input MIDI")

    input_version = _lookup_version(client, job.input_version_ids[0])
    work_id = _resolve_work_id(client, input_version.id)

    _update_progress(client, job.id, 0.2, "downloading MIDI")
    midi_bytes = download_version_bytes(input_version, client)

    _update_progress(client, job.id, 0.3, "loading MIDI")
    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))

    transpose_semitones = int(job.parameters.get("transpose_semitones", 0))

    _update_progress(client, job.id, 0.5, "transposing notes")
    if transpose_semitones != 0:
        for instrument in pm.instruments:
            for note in instrument.notes:
                note.pitch = max(0, min(127, note.pitch + transpose_semitones))

    _update_progress(client, job.id, 0.7, "writing transformed MIDI")
    buf = io.BytesIO()
    pm.write(buf)
    transformed_bytes = buf.getvalue()

    _update_progress(client, job.id, 0.8, "storing transformed MIDI")
    storage_key = _job_storage_key(job, "transformed.mid")
    _upload_bytes(client, _STORAGE_BUCKET, storage_key, transformed_bytes, "audio/midi")

    output_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.midi_corrected,
        storage_key,
        transformed_bytes,
        input_version.id,
        job,
        owner_id,
        mime_type="audio/midi",
        label=(
            f"Transposed {transpose_semitones:+d} semitones"
            if transpose_semitones
            else "Copied MIDI take"
        ),
        metadata={"operation": "transpose", "semitones": transpose_semitones},
    )

    # Comparison and the piano roll operate on persisted entities, rather than
    # parsing a browser-only MIDI file.  A transformed take must therefore have
    # the same durable note representation as an understood transcription.
    entity_repo = EntityRepo(client)
    for instrument in pm.instruments:
        for note in instrument.notes:
            entity_repo.create(
                Entity(
                    version_id=output_version_id,
                    kind=EntityKind.note,
                    span=Span(start_seconds=note.start, end_seconds=note.end),
                    note=NoteEntity(
                        pitch=note.pitch,
                        start_seconds=note.start,
                        end_seconds=note.end,
                        velocity=note.velocity,
                    ),
                ),
                owner_id,
            )

    _update_progress(client, job.id, 1.0, "transform complete")
    return [str(output_version_id)]


def handle_variation(job: Job, client) -> list[str]:
    """Create a complete, immutable transposed take from a saved MIDI version.

    This is deliberately a transparent composition operation, not a claim of
    generative composition: it preserves timing and changes pitch by the chosen
    number of semitones.  The result is nevertheless a first-class take with
    playback, notation, note entities, and fresh analysis.
    """
    if not job.input_version_ids:
        raise ValueError("variation requires a MIDI input version")

    transpose_semitones = int(job.parameters.get("transpose_semitones", 0))
    if not -12 <= transpose_semitones <= 12:
        raise ValueError("transpose_semitones must be between -12 and 12")

    _update_progress(client, job.id, 0.05, "preparing a new take")
    midi_ids = handle_transform(job, client)
    midi_version_id = UUID(midi_ids[0])

    # Each follow-on capability receives the newly persisted MIDI take as its
    # input.  Keeping the same durable job gives the user one cancellable,
    # retryable operation while preserving immutable artifact lineage.
    variation_job = job.model_copy(
        update={
            "input_version_ids": [midi_version_id],
            "parameters": {
                "sample_rate": 22050,
                "label": f"Variation playback ({transpose_semitones:+d} semitones)",
            },
        }
    )
    _update_progress(client, job.id, 0.58, "rendering variation playback")
    audio_ids = handle_synthesize(variation_job, client)
    _update_progress(client, job.id, 0.75, "analysing the new take")
    insight_ids = handle_analyze(variation_job, client)
    _update_progress(client, job.id, 0.9, "engraving notation")
    score_ids = handle_score(variation_job, client)
    _update_progress(client, job.id, 1.0, "variation ready")
    return [*midi_ids, *audio_ids, *insight_ids, *score_ids]


def handle_generate_continuation(job: Job, client) -> list[str]:
    """Generate a simple continuation: repeat the ending bars shifted up
    an octave as a placeholder for full generation."""
    import copy
    import io

    import pretty_midi

    if not job.input_version_ids:
        raise ValueError("continuation requires at least one input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    _update_progress(client, job.id, 0.1, "looking up input MIDI")

    input_version = _lookup_version(client, job.input_version_ids[0])
    work_id = _resolve_work_id(client, input_version.id)

    _update_progress(client, job.id, 0.2, "downloading MIDI")
    midi_bytes = download_version_bytes(input_version, client)

    _update_progress(client, job.id, 0.3, "loading MIDI")
    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))

    total_duration = pm.get_end_time()
    bars_duration = 8.0
    if total_duration < bars_duration:
        bars_duration = total_duration
    start_time = total_duration - bars_duration

    _update_progress(client, job.id, 0.5, "generating continuation")
    for instrument in pm.instruments:
        new_notes = []
        for note in instrument.notes:
            if note.start >= start_time:
                cont_note = copy.copy(note)
                cont_note.start = note.start + bars_duration
                cont_note.end = note.end + bars_duration
                cont_note.pitch += 12
                new_notes.append(cont_note)
        instrument.notes.extend(new_notes)

    _update_progress(client, job.id, 0.7, "writing continued MIDI")
    buf = io.BytesIO()
    pm.write(buf)
    continued_bytes = buf.getvalue()

    _update_progress(client, job.id, 0.8, "storing continued MIDI")
    storage_key = _job_storage_key(job, "continued.mid")
    _upload_bytes(client, _STORAGE_BUCKET, storage_key, continued_bytes, "audio/midi")

    output_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.midi_corrected,
        storage_key,
        len(continued_bytes),
        input_version.id,
        job,
        owner_id,
        mime_type="audio/midi",
    )

    _update_progress(client, job.id, 1.0, "continuation complete")
    return [str(output_version_id)]


def handle_describe(job: Job, client) -> list[str]:
    """Extract audio descriptors using Essentia (or librosa fallback).

    Computes BPM, key, loudness, and spectral centroid from an audio
    version.  Produces one Insight per descriptor.
    """
    import io

    import numpy as np
    import soundfile as sf

    if not job.input_version_ids:
        raise ValueError("describe requires at least one input version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    _update_progress(client, job.id, 0.1, "looking up input audio")

    input_version = _lookup_version(client, job.input_version_ids[0])

    _update_progress(client, job.id, 0.2, "downloading audio")
    audio_bytes = download_version_bytes(input_version, client)

    _update_progress(client, job.id, 0.3, "loading audio samples")
    audio_data, sr = sf.read(io.BytesIO(audio_bytes))
    if audio_data.ndim > 1:
        audio_data = np.mean(audio_data, axis=1)

    _update_progress(client, job.id, 0.4, "extracting descriptors")
    descriptors = _extract_audio_descriptors(audio_data, float(sr))

    insight_ids: list[str] = []

    _update_progress(client, job.id, 0.5, "storing BPM insight")
    bpm = descriptors.get("bpm")
    if bpm is not None:
        bid = _create_insight(
            client,
            input_version.id,
            "bpm",
            f"Tempo: {bpm} BPM",
            evidence={"bpm": bpm},
            confidence=None,
            job=job,
            owner_id=owner_id,
            method="detected",
        )
        insight_ids.append(str(bid))

    _update_progress(client, job.id, 0.6, "storing key insight")
    key_data = descriptors.get("key")
    if key_data:
        key_conf = key_data.get("confidence")
        kid = _create_insight(
            client,
            input_version.id,
            "key",
            f"Key: {key_data['tonic']} {key_data['mode']}",
            evidence=key_data,
            confidence=float(key_conf) if key_conf is not None else None,
            job=job,
            owner_id=owner_id,
            method="detected",
        )
        insight_ids.append(str(kid))

    _update_progress(client, job.id, 0.7, "storing loudness insight")
    loudness = descriptors.get("loudness")
    if loudness is not None:
        lid = _create_insight(
            client,
            input_version.id,
            "loudness",
            f"Integrated loudness: {loudness:.1f} LUFS",
            evidence={"loudness_lufs": loudness},
            confidence=None,
            job=job,
            owner_id=owner_id,
            method="detected",
        )
        insight_ids.append(str(lid))

    _update_progress(client, job.id, 0.8, "storing spectral centroid insight")
    centroid = descriptors.get("spectral_centroid")
    if centroid is not None:
        cid = _create_insight(
            client,
            input_version.id,
            "spectral_centroid",
            f"Spectral centroid: {centroid:.0f} Hz",
            evidence={"spectral_centroid_hz": centroid},
            confidence=None,
            job=job,
            owner_id=owner_id,
            method="detected",
        )
        insight_ids.append(str(cid))

    _update_progress(client, job.id, 1.0, f"describe complete ({len(insight_ids)} insights)")
    return insight_ids


def register_all_capabilities(worker) -> None:
    """Register every capability handler with *worker*."""
    worker.register("transcribe", "1.0", handle_transcribe)
    worker.register("understand", "1.0", handle_understand)
    worker.register("audio_structure", "1.0", handle_audio_structure)
    worker.register("analyze", "1.0", handle_analyze)
    worker.register("score", "1.0", handle_score)
    worker.register("enhance", "1.0", handle_enhance)
    worker.register("synthesize", "1.0", handle_synthesize)
    worker.register("correct", "1.0", handle_correct)
    worker.register("compare", "1.0", handle_compare)
    worker.register("transform", "1.0", handle_transform)
    worker.register("variation", "1.0", handle_variation)
    worker.register("generate_continuation", "1.0", handle_generate_continuation)
    worker.register("describe", "1.0", handle_describe)

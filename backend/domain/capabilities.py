"""
Capability adapters — wrap OSS music-processing libraries behind the domain
Capability contract.  Each handler is a callable ``f(job: Job, client) -> list[str]``
that can be registered with :class:`JobWorker`.
"""

from __future__ import annotations

import logging
import os
import tempfile
from uuid import UUID

import numpy as np

import analyze
import music_features
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

logger = logging.getLogger("capabilities")

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
    byte_size: int,
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
            byte_size=byte_size,
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
    confidence: float = 1.0,
    job: Job | None = None,
    owner_id: str = "",
) -> UUID:
    """Create an Insight row and return its id."""
    repo = InsightRepo(client)
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
            provenance=(
                {
                    "capability": job.capability.name,
                    "capability_version": job.capability.version,
                }
                if job
                else {}
            ),
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
            "confidence": round(float(key_strength), 3) if key_strength else 0.7,
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
            "input_version_ids": [midi_version_id],
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

    _update_progress(client, job.id, 0.25, "preparing audio")
    audio_bytes = music_features.decode_audio_to_wav(audio_bytes, fmt=fmt)

    _update_progress(client, job.id, 0.3, "transcribing audio")
    result = music_features.transcribe_with_engine(
        audio_bytes,
        fmt="wav",
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
    )

    output_ids: list[str] = []

    _update_progress(client, job.id, 0.6, "storing MIDI output")
    midi_key = _job_storage_key(job, "transcribed.mid")
    _upload_bytes(client, _STORAGE_BUCKET, midi_key, result["midi"], "audio/midi")
    midi_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.midi_performance,
        midi_key,
        len(result["midi"]),
        input_version.id,
        job,
        owner_id,
        mime_type="audio/midi",
        label="Transcription MIDI",
        metadata={
            "note_count": len(result.get("notes", [])),
            "cleanup": result.get("cleanup_report", {}),
            "representation": "performance_midi",
            "quality_notice": (
                "Conservatively filtered transcription; timing is preserved rather than quantized."
            ),
        },
    )
    output_ids.append(str(midi_version_id))

    _update_progress(client, job.id, 0.7, "storing note entities")
    note_entities: list[Entity] = []
    for item in result.get("notes", []):
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
                ),
                label=f"MIDI {int(item['pitch'])}",
            )
        )
    EntityRepo(client).create_many(note_entities, owner_id)

    _update_progress(client, job.id, 0.8, "storing rendered audio")
    wav_key = _job_storage_key(job, "transcribed.wav")
    _upload_bytes(client, _STORAGE_BUCKET, wav_key, result["wav"], "audio/wav")
    audio_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.audio_rendered,
        wav_key,
        len(result["wav"]),
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
    result = music_features.structure_with_engine(wav_bytes)

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
                span=Span(start_seconds=segment.start, end_seconds=segment.end),
                label=f"{segment.label.title()} {index + 1}",
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
                confidence=0.65,
                job=job,
                owner_id=owner_id,
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
                confidence=0.7,
                job=job,
                owner_id=owner_id,
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
                    segment.label.title(),
                    evidence={
                        "label": segment.label,
                        "start_seconds": segment.start,
                        "end_seconds": segment.end,
                        "engine": result.engine,
                        "model": result.model,
                    },
                    span=Span(start_seconds=segment.start, end_seconds=segment.end),
                    confidence=0.6,
                    job=job,
                    owner_id=owner_id,
                )
            )
        )
    _update_progress(client, job.id, 1.0, "audio structure analysis complete")
    return insight_ids


def handle_analyze(job: Job, client) -> list[str]:
    """Analyze MIDI → insights for key, tempo, time signature, chords,
    Roman numerals, and cadences."""
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

    _update_progress(client, job.id, 0.3, "running analysis")
    try:
        analysis = analyze.analyze_midi(midi_path)
    finally:
        os.unlink(midi_path)

    insight_ids: list[str] = []

    # Key
    _update_progress(client, job.id, 0.45, "storing key insight")
    key_data = analysis.get("key", {}) or {}
    tonic = key_data.get("tonic", "?")
    mode = key_data.get("mode", "?")
    key_conf = float(key_data.get("confidence", 0.0))
    kid = _create_insight(
        client,
        input_version.id,
        "key",
        f"Key: {tonic} {mode}",
        evidence={"tonic": tonic, "mode": mode},
        confidence=key_conf,
        job=job,
        owner_id=owner_id,
    )
    insight_ids.append(str(kid))

    # Tempo
    _update_progress(client, job.id, 0.50, "storing tempo insight")
    tempo_data = analysis.get("tempo", {}) or {}
    if tempo_data:
        bpm = float(tempo_data.get("bpm", 0))
        tempo_conf = float(tempo_data.get("confidence", 0.0))
        tid = _create_insight(
            client,
            input_version.id,
            "tempo",
            f"Tempo: {bpm} BPM",
            evidence={"bpm": bpm},
            confidence=tempo_conf,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(tid))

    # Time signature
    _update_progress(client, job.id, 0.55, "storing time signature insight")
    ts_data = analysis.get("time_signature", {}) or {}
    if ts_data:
        num = int(ts_data.get("numerator", 4))
        den = int(ts_data.get("denominator", 4))
        ts_conf = float(ts_data.get("confidence", 0.0))
        tsid = _create_insight(
            client,
            input_version.id,
            "time_signature",
            f"Time Signature: {num}/{den}",
            evidence={"numerator": num, "denominator": den},
            confidence=ts_conf,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(tsid))

    # Chords
    chords = analysis.get("chords", []) or []
    chord_count = len(chords)
    for idx, ch in enumerate(chords):
        pct = 0.60 + 0.15 * (idx / max(chord_count, 1))
        _update_progress(
            client,
            job.id,
            pct,
            f"storing chord insight {idx + 1}/{chord_count}",
        )
        root = ch.get("root", "?")
        quality = ch.get("quality", "?")
        start = float(ch.get("start", 0))
        end = float(ch.get("end", 0))
        cid = _create_insight(
            client,
            input_version.id,
            "chord",
            f"{root}:{quality}",
            evidence=ch,
            span=Span(start_beat=start, end_beat=end),
            confidence=0.85,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(cid))

    # Roman numerals
    rns = analysis.get("roman_numerals", []) or []
    rn_count = len(rns)
    for idx, rn in enumerate(rns):
        pct = 0.75 + 0.12 * (idx / max(rn_count, 1))
        _update_progress(
            client,
            job.id,
            pct,
            f"storing roman numeral insight {idx + 1}/{rn_count}",
        )
        figure = rn.get("figure", "?")
        start = float(rn.get("start", 0))
        end = float(rn.get("end", 0))
        rid = _create_insight(
            client,
            input_version.id,
            "roman_numeral",
            figure,
            evidence=rn,
            span=Span(start_beat=start, end_beat=end),
            confidence=0.8,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(rid))

    # Cadences
    cadences = analysis.get("cadences", []) or []
    cad_count = len(cadences)
    for idx, cad in enumerate(cadences):
        pct = 0.87 + 0.1 * (idx / max(cad_count, 1))
        _update_progress(
            client,
            job.id,
            pct,
            f"storing cadence insight {idx + 1}/{cad_count}",
        )
        cad_type = cad.get("type", "?")
        chords_str = " → ".join(cad.get("chords", []))
        position = float(cad.get("position", 0))
        caid = _create_insight(
            client,
            input_version.id,
            "cadence",
            f"{cad_type}: {chords_str}",
            evidence=cad,
            span=Span(start_beat=position),
            confidence=0.8,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(caid))

    # Rhythm: compact, evidence-backed observations instead of a wall of cards.
    rhythm = analysis.get("rhythm") or {}
    if rhythm:
        rid = _create_insight(
            client,
            input_version.id,
            "rhythm",
            (
                f"{rhythm.get('rhythmic_density', 0)} notes/sec · "
                f"{round(float(rhythm.get('syncopation_ratio', 0)) * 100)}% "
                "off-beat on the inferred grid"
            ),
            evidence=rhythm,
            confidence=0.65,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(rid))

    melody = analysis.get("melody") or {}
    if melody:
        mid = _create_insight(
            client,
            input_version.id,
            "melody",
            f"Range: MIDI {melody.get('low_pitch')}–{melody.get('high_pitch')} · "
            f"{round(float(melody.get('stepwise_ratio', 0)) * 100)}% "
            "stepwise motion",
            evidence=melody,
            confidence=0.6,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(mid))

    voice_leading = analysis.get("voice_leading") or {}
    if voice_leading:
        vid = _create_insight(
            client,
            input_version.id,
            "voice_leading",
            voice_leading.get("motion_summary", "Voice-leading summary"),
            evidence=voice_leading,
            confidence=0.55,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(vid))

    for modulation in (analysis.get("modulations") or [])[:12]:
        position = float(modulation.get("position", 0))
        mid = _create_insight(
            client,
            input_version.id,
            "modulation",
            f"{modulation.get('from_key', '?')} → {modulation.get('to_key', '?')}",
            evidence=modulation,
            span=Span(start_seconds=position),
            confidence=0.5,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(mid))

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
        except Exception:
            logger.exception("score_beat_tracking_failed")
    notation_result = music_features.notation_with_engine(midi_bytes, beat_times)
    notation_midi = notation_result["notation_midi"]
    notation_report = notation_result["quantization_report"]
    _update_progress(client, job.id, 0.5, "creating notation")
    notation_key = _job_storage_key(job, "notation.mid")
    _upload_bytes(client, _STORAGE_BUCKET, notation_key, notation_midi, "audio/midi")
    notation_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.midi_corrected,
        notation_key,
        len(notation_midi),
        input_version.id,
        job,
        owner_id,
        mime_type="audio/midi",
        label="Beat-aligned notation MIDI",
        metadata={"notation": notation_report, "estimated_tempo_bpm": tempo},
    )
    musicxml = music_features.convert_format(notation_midi, "midi", "musicxml", notation_ready=True)
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
        len(musicxml),
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
    _update_progress(client, job.id, 1.0, "score complete")
    return [str(notation_version_id), str(version_id)]


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
        len(enhanced),
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
        len(wav_bytes),
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
        len(corrected_bytes),
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
            confidence=0.95,
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
            confidence=0.95,
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
        len(transformed_bytes),
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
            confidence=0.8,
            job=job,
            owner_id=owner_id,
        )
        insight_ids.append(str(bid))

    _update_progress(client, job.id, 0.6, "storing key insight")
    key_data = descriptors.get("key")
    if key_data:
        kid = _create_insight(
            client,
            input_version.id,
            "key",
            f"Key: {key_data['tonic']} {key_data['mode']}",
            evidence=key_data,
            confidence=float(key_data.get("confidence", 0.7)),
            job=job,
            owner_id=owner_id,
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
            confidence=0.85,
            job=job,
            owner_id=owner_id,
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
            confidence=0.85,
            job=job,
            owner_id=owner_id,
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

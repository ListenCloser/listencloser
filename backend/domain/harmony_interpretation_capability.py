"""Bounded alternate Harmony execution over exact audio/MIDI Versions."""

from __future__ import annotations

import logging
from typing import Any

import music_features
from domain.capabilities import (
    _create_insight,
    _lookup_version,
    _merge_adjacent_identical_chords,
    _resolve_owner_id,
    _update_progress,
    download_version_bytes,
)
from domain.models import Job, Span
from engines.registry import get_harmony_engine

logger = logging.getLogger("harmony_interpretation")


def handle_harmony_interpretation(job: Job, client) -> list[str]:
    """Run ChordMini and publish literal chord spans only.

    ChordMini remains an experimental alternate interpretation. It never emits
    or authorizes key, Roman numeral, function, cadence, or voice-leading truth.
    """
    if len(job.input_version_ids) != 2:
        raise ValueError("harmony_interpretation requires exact MIDI and audio Versions")

    engine_name = str(job.parameters.get("harmony_engine") or "")
    if engine_name != "chordmini":
        raise ValueError("unsupported Harmony interpretation engine")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    midi_version = _lookup_version(client, job.input_version_ids[0])
    audio_version = _lookup_version(client, job.input_version_ids[1])

    _update_progress(client, job.id, 0.15, "loading exact Harmony inputs")
    midi_bytes = download_version_bytes(midi_version, client)
    audio_bytes = download_version_bytes(audio_version, client)
    wav_bytes = music_features.decode_audio_to_wav(
        audio_bytes,
        fmt=str(job.parameters.get("fmt") or "wav"),
    )

    _update_progress(client, job.id, 0.35, "running ChordMini")
    harmony = get_harmony_engine(engine_name).analyze(
        midi_bytes,
        audio_bytes=wav_bytes,
    )
    chord_provenance = harmony.component_provenance.get("chords")
    if chord_provenance is None or chord_provenance.engine != engine_name:
        raise RuntimeError("ChordMini returned missing or mismatched chord provenance")
    provenance = chord_provenance.to_dict()

    harmonic_chords = [chord for chord in harmony.chords if chord.get("root") not in {"N", "X"}]
    merged_chords = _merge_adjacent_identical_chords(harmonic_chords)

    _update_progress(client, job.id, 0.70, "publishing alternate chord spans")
    insight_ids: list[str] = []
    for chord in merged_chords:
        start = chord.get("start")
        end = chord.get("end")
        if not isinstance(start, int | float) or not isinstance(end, int | float) or end <= start:
            continue
        root = str(chord.get("root") or "?")
        quality = str(chord.get("quality") or "")
        label = f"{root} {quality}".strip()
        insight_id = _create_insight(
            client,
            midi_version.id,
            "chord",
            label,
            evidence={
                "root": root,
                "quality": quality,
                "start_seconds": float(start),
                "end_seconds": float(end),
                "interpretation": engine_name,
                "experimental": True,
            },
            span=Span(start_seconds=float(start), end_seconds=float(end)),
            confidence=None,
            job=job,
            owner_id=owner_id,
            method="detected",
            engine_provenance=provenance,
        )
        insight_ids.append(str(insight_id))

    logger.info(
        "alternate_harmony_persisted",
        extra={
            "engine": engine_name,
            "midi_version_id": str(midi_version.id),
            "audio_version_id": str(audio_version.id),
            "raw_count": len(harmony.chords),
            "persisted_count": len(insight_ids),
        },
    )
    _update_progress(client, job.id, 1.0, "ChordMini interpretation ready")
    return insight_ids


def register_harmony_interpretation_capability(worker: Any) -> None:
    worker.register("harmony_interpretation", "1.0", handle_harmony_interpretation)

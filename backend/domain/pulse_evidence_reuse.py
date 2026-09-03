"""Exact durable pulse evidence reuse between Analyze and Score."""

from __future__ import annotations

import logging
import math
from typing import Any
from uuid import UUID

from domain.repositories import InsightRepo
from engines.registry import get_beat_engine

logger = logging.getLogger("pulse_evidence_reuse")

PULSE_REUSE_CONTRACT_VERSION = "observed_audio_pulse_v1"


def pulse_preprocessing_contract(fmt: str | None) -> dict[str, Any]:
    """Identity for the audio preprocessing that precedes Beat This inference."""
    return {
        "contract_version": PULSE_REUSE_CONTRACT_VERSION,
        "decoder": "decode_audio_to_wav",
        "input_format": fmt,
    }


def enrich_rhythm_pulse_evidence(
    rhythm: dict[str, Any],
    *,
    audio_version_id: UUID,
    fmt: str | None,
    bpm: object,
) -> dict[str, Any]:
    """Attach exact source/preprocessing identity to an observed rhythm grid."""
    evidence = dict(rhythm)
    evidence["pulse_source_audio_version_id"] = str(audio_version_id)
    evidence["pulse_preprocessing"] = pulse_preprocessing_contract(fmt)
    if _positive_finite_number(bpm):
        evidence["pulse_bpm"] = float(bpm)
    return evidence


def _current_beat_provenance() -> dict[str, Any]:
    return get_beat_engine().provenance.to_dict()


def _positive_finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(float(value))
        and float(value) > 0
    )


def _strictly_increasing_seconds(value: object, *, minimum: int) -> list[float] | None:
    if not isinstance(value, list | tuple):
        return None
    seconds: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int | float):
            return None
        point = float(item)
        if not math.isfinite(point) or point < 0:
            return None
        if seconds and point <= seconds[-1]:
            return None
        seconds.append(point)
    return seconds if len(seconds) >= minimum else None


def load_reusable_score_pulse(
    client,
    *,
    midi_version_id: UUID,
    audio_version_id: UUID,
    owner_id: str,
    fmt: str | None,
) -> dict[str, Any] | None:
    """Load an exact compatible Analyze pulse or fail closed to fresh inference."""
    expected_preprocessing = pulse_preprocessing_contract(fmt)
    try:
        expected_provenance = _current_beat_provenance()
        insights = InsightRepo(client).list_by_version(midi_version_id, owner_id)
    except Exception:
        logger.exception(
            "score_pulse_evidence_lookup_failed",
            extra={"midi_version_id": str(midi_version_id)},
        )
        return None

    for insight in insights:
        if insight.kind != "rhythm":
            continue
        provenance = insight.provenance or {}
        evidence = insight.evidence or {}
        if provenance.get("capability") != "analyze":
            continue
        if provenance.get("engine") != expected_provenance:
            continue
        if evidence.get("pulse_source_audio_version_id") != str(audio_version_id):
            continue
        if evidence.get("pulse_preprocessing") != expected_preprocessing:
            continue
        if evidence.get("pulse_coordinate_unit") != "seconds":
            continue

        beats = _strictly_increasing_seconds(evidence.get("beats_seconds"), minimum=2)
        raw_downbeats = evidence.get("downbeats_seconds", [])
        downbeats = _strictly_increasing_seconds(raw_downbeats, minimum=0)
        bpm = evidence.get("pulse_bpm")
        if beats is None or downbeats is None or not _positive_finite_number(bpm):
            continue

        return {
            "bpm": float(bpm),
            "beats": beats,
            "downbeats": downbeats,
            "provenance": expected_provenance,
        }
    return None

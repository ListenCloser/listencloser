"""Exact parser-native note identities for Score ↔ performance alignment reports.

Parangonar's relation IDs are meaningful only inside the exact Partitura parse that
produced them. This sidecar preserves the parser-native coordinates needed to bridge
those IDs to another representation without inventing a nearest-time fallback.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.score_performance_alignment import ScorePerformanceAlignment

IDENTITY_SCHEMA_VERSION = 1


class ScoreEventIdentity(BaseModel):
    """Literal Partitura score-note fields for one exact MusicXML Version."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    measure_index: int = Field(ge=0)
    pitch: int = Field(ge=0, le=127)
    onset_beat: float
    duration_beat: float = Field(ge=0.0)
    onset_quarter: float
    duration_quarter: float = Field(ge=0.0)
    onset_div: int
    duration_div: int = Field(ge=0)
    voice: int | None = None
    staff: int | None = None
    is_grace: bool = False
    rel_onset_div: int | None = None
    total_measure_divs: int | None = None


class PerformanceEventIdentity(BaseModel):
    """Literal Partitura performed-note fields for one exact MIDI Version."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    pitch: int = Field(ge=0, le=127)
    onset_seconds: float
    duration_seconds: float = Field(ge=0.0)
    velocity: int = Field(ge=0, le=127)
    track: int | None = None
    channel: int | None = None


class AlignmentEventIdentity(BaseModel):
    """All note identities emitted by the exact parser invocation used for alignment."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = IDENTITY_SCHEMA_VERSION
    score_events: tuple[ScoreEventIdentity, ...]
    performance_events: tuple[PerformanceEventIdentity, ...]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> AlignmentEventIdentity:
        score_ids = [event.event_id for event in self.score_events]
        performance_ids = [event.event_id for event in self.performance_events]
        if len(score_ids) != len(set(score_ids)):
            raise ValueError("score event identities must have unique event IDs")
        if len(performance_ids) != len(set(performance_ids)):
            raise ValueError("performance event identities must have unique event IDs")
        return self


def build_alignment_report(
    relation: ScorePerformanceAlignment,
    event_identity: AlignmentEventIdentity,
) -> dict[str, Any]:
    """Add identity information without changing the existing relation root contract."""

    relation_score_ids = {
        event.event_id
        for item in relation.relations
        for event in item.score_events
    }
    relation_performance_ids = {
        event.event_id
        for item in relation.relations
        for event in item.performance_events
    }
    identity_score_ids = {event.event_id for event in event_identity.score_events}
    identity_performance_ids = {event.event_id for event in event_identity.performance_events}

    if not relation_score_ids.issubset(identity_score_ids):
        raise ValueError("alignment relation references score events missing identity descriptors")
    if not relation_performance_ids.issubset(identity_performance_ids):
        raise ValueError("alignment relation references performance events missing identity descriptors")

    payload = relation.model_dump(mode="json")
    payload["event_identity"] = event_identity.model_dump(mode="json")
    return payload


def canonical_alignment_report_json(
    relation: ScorePerformanceAlignment,
    event_identity: AlignmentEventIdentity,
) -> str:
    """Stable additive report serialization for durable immutable publication."""

    return json.dumps(
        build_alignment_report(relation, event_identity),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

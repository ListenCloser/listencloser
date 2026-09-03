"""Normalized Score ↔ performed-MIDI relation for issue #1083.

This module owns only the relation contract over exact immutable inputs and the
normalization boundary for MAPS-style Parangonar records. It deliberately does
not persist relations, resolve semantic Version authority, or fall back to
shared-seconds proximity. Those responsibilities remain with #613/#807.
"""

from __future__ import annotations

import json
from collections import defaultdict
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AlignmentInputRole(str, Enum):
    written_score = "written_score"
    performed_midi = "performed_midi"


class AlignmentRelationKind(str, Enum):
    matched = "matched"
    score_only = "score_only"
    performance_only = "performance_only"
    grouped = "grouped"


class AlignmentSufficiency(str, Enum):
    sufficient = "sufficient"
    insufficient = "insufficient"
    failed = "failed"


class AlignmentProjectionPrecision(str, Enum):
    """#807-compatible projection truthfulness, scoped to this relation."""

    adequate = "adequate"
    unsupported = "unsupported"


class AlignmentInputVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_id: UUID
    role: AlignmentInputRole


class AlignmentMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    package: str
    package_version: str
    matcher: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AlignmentEventRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    onset_beat: float | None = None
    onset_seconds: float | None = None


class ScorePerformanceEventRelation(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: AlignmentRelationKind
    score_events: tuple[AlignmentEventRef, ...] = ()
    performance_events: tuple[AlignmentEventRef, ...] = ()

    @model_validator(mode="after")
    def validate_cardinality(self) -> "ScorePerformanceEventRelation":
        score_count = len(self.score_events)
        performance_count = len(self.performance_events)
        if self.kind is AlignmentRelationKind.matched and (score_count, performance_count) != (1, 1):
            raise ValueError("matched relation requires exactly one score and one performance event")
        if self.kind is AlignmentRelationKind.score_only and not (score_count >= 1 and performance_count == 0):
            raise ValueError("score_only relation requires score event(s) and no performance event")
        if self.kind is AlignmentRelationKind.performance_only and not (
            score_count == 0 and performance_count >= 1
        ):
            raise ValueError(
                "performance_only relation requires performance event(s) and no score event"
            )
        if self.kind is AlignmentRelationKind.grouped and not (
            score_count >= 1
            and performance_count >= 1
            and (score_count > 1 or performance_count > 1)
        ):
            raise ValueError("grouped relation requires a non-1:1 mapping on at least one side")
        return self


class AlignmentCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    score_events_total: int = Field(ge=0)
    performance_events_total: int = Field(ge=0)
    score_events_mapped: int = Field(ge=0)
    performance_events_mapped: int = Field(ge=0)

    @property
    def score_fraction(self) -> float | None:
        if self.score_events_total == 0:
            return None
        return self.score_events_mapped / self.score_events_total

    @property
    def performance_fraction(self) -> float | None:
        if self.performance_events_total == 0:
            return None
        return self.performance_events_mapped / self.performance_events_total


class AlignmentSufficiencyPolicy(BaseModel):
    """Explicit coverage gate; coverage is observable support, not confidence."""

    model_config = ConfigDict(frozen=True)

    minimum_score_fraction: float = Field(ge=0.0, le=1.0)
    minimum_performance_fraction: float = Field(ge=0.0, le=1.0)


class ScorePerformanceAlignment(BaseModel):
    model_config = ConfigDict(frozen=True)

    score_version_id: UUID
    performance_version_id: UUID
    method: AlignmentMethod
    relations: tuple[ScorePerformanceEventRelation, ...]
    coverage: AlignmentCoverage
    sufficiency_policy: AlignmentSufficiencyPolicy
    sufficiency: AlignmentSufficiency
    projection_precision: AlignmentProjectionPrecision
    failure: str | None = None

    @model_validator(mode="after")
    def validate_truthfulness(self) -> "ScorePerformanceAlignment":
        if self.score_version_id == self.performance_version_id:
            raise ValueError("score and performance must be distinct immutable Versions")
        if self.sufficiency is AlignmentSufficiency.sufficient:
            if self.failure is not None:
                raise ValueError("sufficient alignment cannot carry a failure")
            if self.projection_precision is not AlignmentProjectionPrecision.adequate:
                raise ValueError("sufficient alignment must project as adequate")
        else:
            if self.projection_precision is not AlignmentProjectionPrecision.unsupported:
                raise ValueError("failed/insufficient alignment must project as unsupported")
        if self.sufficiency is AlignmentSufficiency.failed and self.failure is None:
            raise ValueError("failed alignment must record its failure")
        return self

    def canonical_json(self) -> str:
        """Stable serialization for reproducible relation/provenance snapshots."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def _event_ref(
    event_id: str,
    *,
    onset_beat_by_id: dict[str, float],
    onset_seconds_by_id: dict[str, float],
    score: bool,
) -> AlignmentEventRef:
    return AlignmentEventRef(
        event_id=event_id,
        onset_beat=onset_beat_by_id.get(event_id) if score else None,
        onset_seconds=onset_seconds_by_id.get(event_id) if not score else None,
    )


def _failed_alignment(
    *,
    score_input: AlignmentInputVersion,
    performance_input: AlignmentInputVersion,
    method: AlignmentMethod,
    policy: AlignmentSufficiencyPolicy,
    score_event_ids: set[str],
    performance_event_ids: set[str],
    failure: str,
) -> ScorePerformanceAlignment:
    return ScorePerformanceAlignment(
        score_version_id=score_input.version_id,
        performance_version_id=performance_input.version_id,
        method=method,
        relations=(),
        coverage=AlignmentCoverage(
            score_events_total=len(score_event_ids),
            performance_events_total=len(performance_event_ids),
            score_events_mapped=0,
            performance_events_mapped=0,
        ),
        sufficiency_policy=policy,
        sufficiency=AlignmentSufficiency.failed,
        projection_precision=AlignmentProjectionPrecision.unsupported,
        failure=failure,
    )


def normalize_parangonar_alignment(
    *,
    score_input: AlignmentInputVersion,
    performance_input: AlignmentInputVersion,
    raw_alignment: list[dict[str, Any]] | None,
    package_version: str,
    matcher: str,
    parameters: dict[str, Any] | None,
    score_event_ids: set[str],
    performance_event_ids: set[str],
    score_onset_beat_by_id: dict[str, float] | None = None,
    performance_onset_seconds_by_id: dict[str, float] | None = None,
    sufficiency_policy: AlignmentSufficiencyPolicy,
    matcher_failure: str | None = None,
) -> ScorePerformanceAlignment:
    """Normalize Parangonar's MAPS-style output without altering either input.

    A caller must supply already-resolved semantic roles. This function does not
    infer authority from Artifact kind/recency; until #613 lands, ambiguity must
    fail before this boundary.
    """

    if score_input.role is not AlignmentInputRole.written_score:
        raise ValueError("score input is not authorized as a written-score Version")
    if performance_input.role is not AlignmentInputRole.performed_midi:
        raise ValueError("performance input is not authorized as a performed-MIDI Version")
    if score_input.version_id == performance_input.version_id:
        raise ValueError("score and performance must be distinct immutable Versions")

    method = AlignmentMethod(
        package="parangonar",
        package_version=package_version,
        matcher=matcher,
        parameters=parameters or {},
    )
    score_onsets = score_onset_beat_by_id or {}
    performance_onsets = performance_onset_seconds_by_id or {}

    if matcher_failure is not None:
        return _failed_alignment(
            score_input=score_input,
            performance_input=performance_input,
            method=method,
            policy=sufficiency_policy,
            score_event_ids=score_event_ids,
            performance_event_ids=performance_event_ids,
            failure=matcher_failure,
        )
    if raw_alignment is None:
        return _failed_alignment(
            score_input=score_input,
            performance_input=performance_input,
            method=method,
            policy=sufficiency_policy,
            score_event_ids=score_event_ids,
            performance_event_ids=performance_event_ids,
            failure="matcher returned no alignment",
        )

    matched_edges: set[tuple[str, str]] = set()
    declared_score_only: set[str] = set()
    declared_performance_only: set[str] = set()
    for record in raw_alignment:
        label = record.get("label")
        if label == "match":
            score_id = str(record.get("score_id"))
            performance_id = str(record.get("performance_id"))
            if score_id not in score_event_ids or performance_id not in performance_event_ids:
                return _failed_alignment(
                    score_input=score_input,
                    performance_input=performance_input,
                    method=method,
                    policy=sufficiency_policy,
                    score_event_ids=score_event_ids,
                    performance_event_ids=performance_event_ids,
                    failure="matcher referenced an event outside the exact input Versions",
                )
            matched_edges.add((score_id, performance_id))
        elif label == "deletion":
            score_id = str(record.get("score_id"))
            if score_id not in score_event_ids:
                return _failed_alignment(
                    score_input=score_input,
                    performance_input=performance_input,
                    method=method,
                    policy=sufficiency_policy,
                    score_event_ids=score_event_ids,
                    performance_event_ids=performance_event_ids,
                    failure="matcher deletion referenced an event outside the score Version",
                )
            declared_score_only.add(score_id)
        elif label == "insertion":
            performance_id = str(record.get("performance_id"))
            if performance_id not in performance_event_ids:
                return _failed_alignment(
                    score_input=score_input,
                    performance_input=performance_input,
                    method=method,
                    policy=sufficiency_policy,
                    score_event_ids=score_event_ids,
                    performance_event_ids=performance_event_ids,
                    failure="matcher insertion referenced an event outside the performance Version",
                )
            declared_performance_only.add(performance_id)
        else:
            return _failed_alignment(
                score_input=score_input,
                performance_input=performance_input,
                method=method,
                policy=sufficiency_policy,
                score_event_ids=score_event_ids,
                performance_event_ids=performance_event_ids,
                failure=f"unsupported matcher relation label: {label!r}",
            )

    score_neighbors: defaultdict[str, set[str]] = defaultdict(set)
    performance_neighbors: defaultdict[str, set[str]] = defaultdict(set)
    for score_id, performance_id in matched_edges:
        score_neighbors[score_id].add(performance_id)
        performance_neighbors[performance_id].add(score_id)

    relations: list[ScorePerformanceEventRelation] = []
    seen_score: set[str] = set()
    seen_performance: set[str] = set()

    # Collapse connected duplicate match edges into one explicit grouped relation.
    # Released DualDTWNoteMatcher is 1:1 by construction, but the product contract
    # remains truthful if a future maintained matcher emits non-1:1 assignments.
    for starting_score in sorted(score_neighbors):
        if starting_score in seen_score:
            continue
        component_scores: set[str] = set()
        component_performances: set[str] = set()
        score_stack = [starting_score]
        while score_stack:
            score_id = score_stack.pop()
            if score_id in component_scores:
                continue
            component_scores.add(score_id)
            for performance_id in score_neighbors[score_id]:
                if performance_id in component_performances:
                    continue
                component_performances.add(performance_id)
                score_stack.extend(performance_neighbors[performance_id] - component_scores)

        seen_score.update(component_scores)
        seen_performance.update(component_performances)
        kind = (
            AlignmentRelationKind.matched
            if len(component_scores) == 1 and len(component_performances) == 1
            else AlignmentRelationKind.grouped
        )
        relations.append(
            ScorePerformanceEventRelation(
                kind=kind,
                score_events=tuple(
                    _event_ref(
                        event_id,
                        onset_beat_by_id=score_onsets,
                        onset_seconds_by_id=performance_onsets,
                        score=True,
                    )
                    for event_id in sorted(component_scores)
                ),
                performance_events=tuple(
                    _event_ref(
                        event_id,
                        onset_beat_by_id=score_onsets,
                        onset_seconds_by_id=performance_onsets,
                        score=False,
                    )
                    for event_id in sorted(component_performances)
                ),
            )
        )

    mapped_scores = set(score_neighbors)
    mapped_performances = set(performance_neighbors)
    # The matcher may redundantly declare a deletion/insertion that also appears
    # in a match only if its output is internally inconsistent; fail closed.
    if mapped_scores & declared_score_only or mapped_performances & declared_performance_only:
        return _failed_alignment(
            score_input=score_input,
            performance_input=performance_input,
            method=method,
            policy=sufficiency_policy,
            score_event_ids=score_event_ids,
            performance_event_ids=performance_event_ids,
            failure="matcher returned contradictory matched and unmatched event records",
        )

    score_only = (score_event_ids - mapped_scores) | declared_score_only
    performance_only = (performance_event_ids - mapped_performances) | declared_performance_only
    for event_id in sorted(score_only):
        relations.append(
            ScorePerformanceEventRelation(
                kind=AlignmentRelationKind.score_only,
                score_events=(
                    _event_ref(
                        event_id,
                        onset_beat_by_id=score_onsets,
                        onset_seconds_by_id=performance_onsets,
                        score=True,
                    ),
                ),
            )
        )
    for event_id in sorted(performance_only):
        relations.append(
            ScorePerformanceEventRelation(
                kind=AlignmentRelationKind.performance_only,
                performance_events=(
                    _event_ref(
                        event_id,
                        onset_beat_by_id=score_onsets,
                        onset_seconds_by_id=performance_onsets,
                        score=False,
                    ),
                ),
            )
        )

    coverage = AlignmentCoverage(
        score_events_total=len(score_event_ids),
        performance_events_total=len(performance_event_ids),
        score_events_mapped=len(mapped_scores),
        performance_events_mapped=len(mapped_performances),
    )
    score_fraction = coverage.score_fraction
    performance_fraction = coverage.performance_fraction
    sufficient = (
        score_fraction is not None
        and performance_fraction is not None
        and score_fraction >= sufficiency_policy.minimum_score_fraction
        and performance_fraction >= sufficiency_policy.minimum_performance_fraction
    )
    return ScorePerformanceAlignment(
        score_version_id=score_input.version_id,
        performance_version_id=performance_input.version_id,
        method=method,
        relations=tuple(
            sorted(
                relations,
                key=lambda relation: (
                    relation.kind.value,
                    tuple(event.event_id for event in relation.score_events),
                    tuple(event.event_id for event in relation.performance_events),
                ),
            )
        ),
        coverage=coverage,
        sufficiency_policy=sufficiency_policy,
        sufficiency=(
            AlignmentSufficiency.sufficient if sufficient else AlignmentSufficiency.insufficient
        ),
        projection_precision=(
            AlignmentProjectionPrecision.adequate
            if sufficient
            else AlignmentProjectionPrecision.unsupported
        ),
        failure=None,
    )

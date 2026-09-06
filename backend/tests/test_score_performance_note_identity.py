from __future__ import annotations

from uuid import uuid4

import pytest

from domain.score_performance_alignment import (
    AlignmentCoverage,
    AlignmentEventRef,
    AlignmentMethod,
    AlignmentProjectionPrecision,
    AlignmentRelationKind,
    AlignmentSufficiency,
    AlignmentSufficiencyPolicy,
    ScorePerformanceAlignment,
    ScorePerformanceEventRelation,
)
from domain.score_performance_note_identity import (
    AlignmentEventIdentity,
    PerformanceEventIdentity,
    ScoreEventIdentity,
    build_alignment_report,
)
from engines.alignment._parangonar_runner import _measure_index
from engines.alignment.parangonar import _event_identity


def _relation() -> ScorePerformanceAlignment:
    return ScorePerformanceAlignment(
        score_version_id=uuid4(),
        performance_version_id=uuid4(),
        method=AlignmentMethod(
            package="parangonar",
            package_version="3.3.3",
            matcher="DualDTWNoteMatcher",
        ),
        relations=(
            ScorePerformanceEventRelation(
                kind=AlignmentRelationKind.matched,
                score_events=(AlignmentEventRef(event_id="s1", onset_beat=0.0),),
                performance_events=(AlignmentEventRef(event_id="p1", onset_seconds=0.1),),
            ),
        ),
        coverage=AlignmentCoverage(
            score_events_total=1,
            performance_events_total=1,
            score_events_mapped=1,
            performance_events_mapped=1,
        ),
        sufficiency_policy=AlignmentSufficiencyPolicy(
            minimum_score_fraction=0.8,
            minimum_performance_fraction=0.8,
        ),
        sufficiency=AlignmentSufficiency.sufficient,
        projection_precision=AlignmentProjectionPrecision.adequate,
    )


def _score_identity(event_id: str = "s1") -> ScoreEventIdentity:
    return ScoreEventIdentity(
        event_id=event_id,
        measure_index=0,
        pitch=60,
        onset_beat=0.0,
        duration_beat=1.0,
        onset_quarter=0.0,
        duration_quarter=1.0,
        onset_div=0,
        duration_div=480,
        voice=1,
        staff=1,
        rel_onset_div=0,
        total_measure_divs=1920,
    )


def _performance_identity(event_id: str = "p1") -> PerformanceEventIdentity:
    return PerformanceEventIdentity(
        event_id=event_id,
        pitch=60,
        onset_seconds=0.1,
        duration_seconds=0.45,
        velocity=88,
        track=0,
        channel=0,
    )


def test_identity_bundle_rejects_duplicate_parser_ids():
    with pytest.raises(ValueError, match="score event identities must have unique"):
        AlignmentEventIdentity(
            score_events=(_score_identity(), _score_identity()),
            performance_events=(_performance_identity(),),
        )


def test_report_fails_closed_when_relation_identity_is_missing():
    identity = AlignmentEventIdentity(
        score_events=(_score_identity("other-score"),),
        performance_events=(_performance_identity(),),
    )
    with pytest.raises(ValueError, match="score events missing identity descriptors"):
        build_alignment_report(_relation(), identity)


def test_measure_identity_uses_full_parser_order_not_note_order():
    intervals = [(0, 1920), (1920, 3840), (3840, 5760)]
    assert _measure_index(0, intervals) == 0
    assert _measure_index(2400, intervals) == 1
    assert _measure_index(3840, intervals) == 2
    with pytest.raises(RuntimeError, match="outside parsed measure bounds"):
        _measure_index(6000, intervals)


def test_runner_identity_parser_preserves_native_score_and_performance_fields():
    payload = {
        "score_events": [
            {
                "id": "s1",
                "onset": 4.0,
                "measure_index": 3,
                "pitch": 64,
                "onset_beat": 4.0,
                "duration_beat": 0.5,
                "onset_quarter": 4.0,
                "duration_quarter": 0.5,
                "onset_div": 1920,
                "duration_div": 240,
                "voice": 2,
                "staff": 1,
                "is_grace": False,
                "rel_onset_div": 0,
                "total_measure_divs": 1920,
            }
        ],
        "performance_events": [
            {
                "id": "p1",
                "onset": 0.12,
                "pitch": 64,
                "onset_seconds": 0.12,
                "duration_seconds": 0.31,
                "velocity": 99,
                "track": 1,
                "channel": 2,
            }
        ],
    }

    identity = _event_identity(payload)

    assert identity.score_events[0].event_id == "s1"
    assert identity.score_events[0].measure_index == 3
    assert identity.score_events[0].pitch == 64
    assert identity.score_events[0].duration_div == 240
    assert identity.score_events[0].voice == 2
    assert identity.performance_events[0].event_id == "p1"
    assert identity.performance_events[0].onset_seconds == 0.12
    assert identity.performance_events[0].velocity == 99
    assert identity.performance_events[0].channel == 2

from __future__ import annotations

from uuid import uuid4

import pytest

from domain import score_performance_alignment as alignment

AlignmentInputRole = alignment.AlignmentInputRole
AlignmentInputVersion = alignment.AlignmentInputVersion
AlignmentProjectionPrecision = alignment.AlignmentProjectionPrecision
AlignmentRelationKind = alignment.AlignmentRelationKind
AlignmentSufficiency = alignment.AlignmentSufficiency
AlignmentSufficiencyPolicy = alignment.AlignmentSufficiencyPolicy
normalize_parangonar_alignment = alignment.normalize_parangonar_alignment

POLICY = AlignmentSufficiencyPolicy(
    minimum_score_fraction=0.8,
    minimum_performance_fraction=0.8,
)


def _inputs():
    return (
        AlignmentInputVersion(version_id=uuid4(), role=AlignmentInputRole.written_score),
        AlignmentInputVersion(version_id=uuid4(), role=AlignmentInputRole.performed_midi),
    )


def _normalize(
    raw_alignment,
    *,
    score_ids=("s1",),
    performance_ids=("p1",),
    policy=POLICY,
    matcher_failure=None,
):
    score_input, performance_input = _inputs()
    return normalize_parangonar_alignment(
        score_input=score_input,
        performance_input=performance_input,
        raw_alignment=raw_alignment,
        package_version="3.3.3",
        matcher="DualDTWNoteMatcher",
        parameters={"process_ornaments": False},
        score_event_ids=set(score_ids),
        performance_event_ids=set(performance_ids),
        score_onset_beat_by_id={event_id: float(index) for index, event_id in enumerate(score_ids)},
        performance_onset_seconds_by_id={
            event_id: index * 0.48 for index, event_id in enumerate(performance_ids)
        },
        sufficiency_policy=policy,
        matcher_failure=matcher_failure,
    )


def test_normalizes_simple_one_to_one_with_timing_and_exact_versions():
    alignment_result = _normalize(
        [{"label": "match", "score_id": "s1", "performance_id": "p1"}]
    )

    assert alignment_result.sufficiency is AlignmentSufficiency.sufficient
    assert alignment_result.projection_precision is AlignmentProjectionPrecision.adequate
    assert alignment_result.coverage.score_fraction == 1.0
    assert alignment_result.coverage.performance_fraction == 1.0
    assert len(alignment_result.relations) == 1
    relation = alignment_result.relations[0]
    assert relation.kind is AlignmentRelationKind.matched
    assert relation.score_events[0].event_id == "s1"
    assert relation.score_events[0].onset_beat == 0.0
    assert relation.performance_events[0].event_id == "p1"
    assert relation.performance_events[0].onset_seconds == 0.0
    assert alignment_result.score_version_id != alignment_result.performance_version_id


def test_preserves_score_only_and_performance_only_without_timestamp_fallback():
    alignment_result = _normalize(
        [
            {"label": "match", "score_id": "s1", "performance_id": "p1"},
            {"label": "deletion", "score_id": "s2"},
            {"label": "insertion", "performance_id": "p2"},
        ],
        score_ids=("s1", "s2"),
        performance_ids=("p1", "p2"),
        policy=AlignmentSufficiencyPolicy(
            minimum_score_fraction=0.5,
            minimum_performance_fraction=0.5,
        ),
    )

    kinds = {relation.kind for relation in alignment_result.relations}
    assert kinds == {
        AlignmentRelationKind.matched,
        AlignmentRelationKind.score_only,
        AlignmentRelationKind.performance_only,
    }
    assert alignment_result.coverage.score_fraction == 0.5
    assert alignment_result.coverage.performance_fraction == 0.5


def test_collapses_non_one_to_one_match_edges_into_explicit_grouped_relation():
    alignment_result = _normalize(
        [
            {"label": "match", "score_id": "s1", "performance_id": "p1"},
            {"label": "match", "score_id": "s1", "performance_id": "p2"},
        ],
        performance_ids=("p1", "p2"),
    )

    assert len(alignment_result.relations) == 1
    relation = alignment_result.relations[0]
    assert relation.kind is AlignmentRelationKind.grouped
    assert [event.event_id for event in relation.score_events] == ["s1"]
    assert [event.event_id for event in relation.performance_events] == ["p1", "p2"]


def test_incompatible_semantic_version_inputs_fail_closed():
    score_input = AlignmentInputVersion(
        version_id=uuid4(),
        role=AlignmentInputRole.performed_midi,
    )
    performance_input = AlignmentInputVersion(
        version_id=uuid4(),
        role=AlignmentInputRole.performed_midi,
    )

    with pytest.raises(ValueError, match="written-score Version"):
        normalize_parangonar_alignment(
            score_input=score_input,
            performance_input=performance_input,
            raw_alignment=[],
            package_version="3.3.3",
            matcher="DualDTWNoteMatcher",
            parameters={},
            score_event_ids=set(),
            performance_event_ids=set(),
            sufficiency_policy=POLICY,
        )


def test_same_version_cannot_cross_score_and_performance_authority():
    version_id = uuid4()
    with pytest.raises(ValueError, match="distinct immutable Versions"):
        normalize_parangonar_alignment(
            score_input=AlignmentInputVersion(
                version_id=version_id,
                role=AlignmentInputRole.written_score,
            ),
            performance_input=AlignmentInputVersion(
                version_id=version_id,
                role=AlignmentInputRole.performed_midi,
            ),
            raw_alignment=[],
            package_version="3.3.3",
            matcher="DualDTWNoteMatcher",
            parameters={},
            score_event_ids=set(),
            performance_event_ids=set(),
            sufficiency_policy=POLICY,
        )


def test_matcher_failure_is_explicit_and_projection_is_unsupported():
    alignment_result = _normalize(
        None,
        matcher_failure="IndexError: degenerate score input",
    )

    assert alignment_result.sufficiency is AlignmentSufficiency.failed
    assert alignment_result.projection_precision is AlignmentProjectionPrecision.unsupported
    assert alignment_result.failure == "IndexError: degenerate score input"
    assert alignment_result.relations == ()


def test_malformed_matcher_output_outside_exact_inputs_fails_closed():
    alignment_result = _normalize(
        [{"label": "match", "score_id": "other", "performance_id": "p1"}]
    )

    assert alignment_result.sufficiency is AlignmentSufficiency.failed
    assert alignment_result.projection_precision is AlignmentProjectionPrecision.unsupported
    assert "outside the exact input Versions" in alignment_result.failure


def test_empty_or_incomplete_alignment_cannot_masquerade_as_adequate():
    alignment_result = _normalize(
        [],
        score_ids=("s1", "s2"),
        performance_ids=("p1", "p2"),
    )

    assert alignment_result.coverage.score_fraction == 0.0
    assert alignment_result.coverage.performance_fraction == 0.0
    assert alignment_result.sufficiency is AlignmentSufficiency.insufficient
    assert alignment_result.projection_precision is AlignmentProjectionPrecision.unsupported


def test_serialization_and_provenance_are_deterministic_without_generic_confidence():
    score_input, performance_input = _inputs()
    common = dict(
        score_input=score_input,
        performance_input=performance_input,
        package_version="3.3.3",
        matcher="DualDTWNoteMatcher",
        parameters={"z": 2, "a": 1},
        score_event_ids={"s1", "s2"},
        performance_event_ids={"p1", "p2"},
        sufficiency_policy=AlignmentSufficiencyPolicy(
            minimum_score_fraction=0.5,
            minimum_performance_fraction=0.5,
        ),
    )
    records = [
        {"label": "match", "score_id": "s1", "performance_id": "p1"},
        {"label": "deletion", "score_id": "s2"},
        {"label": "insertion", "performance_id": "p2"},
    ]

    first = normalize_parangonar_alignment(raw_alignment=records, **common)
    second = normalize_parangonar_alignment(raw_alignment=list(reversed(records)), **common)

    assert first.canonical_json() == second.canonical_json()
    payload = first.model_dump(mode="json")
    assert payload["score_version_id"] == str(score_input.version_id)
    assert payload["performance_version_id"] == str(performance_input.version_id)
    assert payload["method"] == {
        "package": "parangonar",
        "package_version": "3.3.3",
        "matcher": "DualDTWNoteMatcher",
        "parameters": {"z": 2, "a": 1},
    }
    assert "confidence" not in first.canonical_json()
    assert "supersede" not in first.canonical_json()

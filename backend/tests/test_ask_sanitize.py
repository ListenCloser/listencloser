"""Deterministic server-side reference/action validation tests."""

from __future__ import annotations

from ask.contracts import (
    AskInsightReference,
    AskMeasureReference,
    AskNotesReference,
    AskResponse,
    AskSeekAction,
    AskShowRepresentationAction,
    AskTimeReference,
)
from ask.sanitize import sanitize_response


def _response(answer: str = "An answer.", references=None, actions=None) -> AskResponse:
    return AskResponse(answer=answer, references=references or [], suggestedActions=actions or None)


def test_valid_grounded_question_returns_safe_answer(selection_context):
    response = _response(
        references=[AskInsightReference(type="insight", id="insight-selection")],
        actions=[AskShowRepresentationAction(type="show_representation", representationId="score")],
    )
    safe = sanitize_response(response, selection_context)

    assert safe.answer == "An answer."
    assert len(safe.references) == 1
    assert safe.references[0].id == "insight-selection"
    assert safe.suggestedActions is not None
    assert safe.suggestedActions[0].representationId == "score"


def test_invented_insight_reference_is_removed(selection_context):
    response = _response(references=[AskInsightReference(type="insight", id="does-not-exist")])
    safe = sanitize_response(response, selection_context)

    assert safe.references == []


def test_insufficient_evidence_answer_is_accepted(selection_context):
    """An honest 'insufficient evidence' answer with no references stays intact."""
    response = _response(answer="I don't have enough evidence to answer that.", references=[])
    safe = sanitize_response(response, selection_context)

    assert safe.answer == "I don't have enough evidence to answer that."
    assert safe.references == []


def test_invented_note_ids_are_removed(selection_context):
    response = _response(
        references=[
            AskNotesReference(type="notes", ids=["note-1", "ghost-note"]),
        ]
    )
    safe = sanitize_response(response, selection_context)

    # A note reference must be dropped wholesale when ANY id is not grounded in
    # the supplied selection note ids (partial references would silently point
    # at entities the model never saw).
    assert safe.references == []


def test_valid_note_reference_is_kept(selection_context):
    response = _response(
        references=[AskNotesReference(type="notes", ids=["note-1", "note-2"])]
    )
    safe = sanitize_response(response, selection_context)

    assert len(safe.references) == 1
    assert safe.references[0].ids == ["note-1", "note-2"]


def test_notes_reference_dropped_when_context_has_no_selection_note_ids(whole_work_context):
    response = _response(
        references=[AskNotesReference(type="notes", ids=["note-1"])]
    )
    safe = sanitize_response(response, whole_work_context)

    assert safe.references == []


def test_invalid_representation_action_removed(selection_context):
    response = _response(
        actions=[
            AskShowRepresentationAction(type="show_representation", representationId="harmony"),  # type: ignore[arg-type]
        ]
    )
    safe = sanitize_response(response, selection_context)

    assert safe.suggestedActions is None or safe.suggestedActions == []


def test_negative_time_reference_removed(selection_context):
    response = _response(
        references=[AskTimeReference(type="time", start=-4.0, end=8.0, domain="performance")]
    )
    safe = sanitize_response(response, selection_context)

    assert safe.references == []


def test_reversed_time_range_removed(selection_context):
    response = _response(
        references=[AskTimeReference(type="time", start=10.0, end=4.0, domain="performance")]
    )
    safe = sanitize_response(response, selection_context)

    assert safe.references == []


def test_cross_domain_time_reference_removed(selection_context):
    """A time reference in a domain the user is not grounded in is dropped."""
    response = _response(
        references=[AskTimeReference(type="time", start=1.0, end=3.0, domain="notation")]
    )
    safe = sanitize_response(response, selection_context)

    assert safe.references == []


def test_matching_domain_time_reference_kept(selection_context):
    response = _response(
        references=[AskTimeReference(type="time", start=1.0, end=3.0, domain="performance")]
    )
    safe = sanitize_response(response, selection_context)

    assert len(safe.references) == 1


def test_cross_domain_seek_action_removed(selection_context):
    response = _response(
        actions=[AskSeekAction(type="seek", seconds=4.0, domain="notation")]
    )
    safe = sanitize_response(response, selection_context)

    assert safe.suggestedActions is None or safe.suggestedActions == []


def test_matching_domain_seek_action_kept(selection_context):
    response = _response(
        actions=[AskSeekAction(type="seek", seconds=4.0, domain="performance")]
    )
    safe = sanitize_response(response, selection_context)

    assert safe.suggestedActions is not None
    assert safe.suggestedActions[0].seconds == 4.0


def test_measure_reference_with_negative_start_removed(selection_context):
    response = _response(
        references=[AskMeasureReference(type="measure", start=-1, end=3)]
    )
    safe = sanitize_response(response, selection_context)

    assert safe.references == []


def test_measure_reference_with_reversed_range_removed(selection_context):
    response = _response(
        references=[AskMeasureReference(type="measure", start=5, end=3)]
    )
    safe = sanitize_response(response, selection_context)

    assert safe.references == []


def test_valid_measure_reference_kept(selection_context):
    response = _response(
        references=[AskMeasureReference(type="measure", start=2, end=4)]
    )
    safe = sanitize_response(response, selection_context)

    assert len(safe.references) == 1


def test_multiple_invalid_items_do_not_fail_the_whole_answer(selection_context):
    """One bad optional reference never fails the entire response."""
    response = _response(
        references=[
            AskInsightReference(type="insight", id="invented"),
            AskTimeReference(type="time", start=1.0, end=3.0, domain="performance"),
            AskNotesReference(type="notes", ids=["ghost"]),
        ],
        actions=[
            AskShowRepresentationAction(type="show_representation", representationId="piano_roll"),
            AskSeekAction(type="seek", seconds=-1, domain="performance"),
        ],
    )
    safe = sanitize_response(response, selection_context)

    assert safe.answer == "An answer."
    assert len(safe.references) == 1
    assert safe.references[0].type == "time"
    assert len(safe.suggestedActions or []) == 1
    assert safe.suggestedActions[0].type == "show_representation"
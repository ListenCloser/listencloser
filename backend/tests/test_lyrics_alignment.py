from uuid import UUID

from domain.lyrics_alignment import ObservedWord, build_report_from_evidence


def _normalize(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _score(left: str, right: str) -> float:
    if left == right:
        return 100.0
    if (left, right) == ("wurld", "world"):
        return 80.0
    return 0.0


def test_report_preserves_exact_provenance_and_local_alignment_states():
    source_text = "hello wurld\nagain missing"
    work_id = UUID("00000000-0000-0000-0000-000000000001")
    artifact_id = UUID("00000000-0000-0000-0000-000000000002")
    version_id = UUID("00000000-0000-0000-0000-000000000003")
    transcript = [
        ObservedWord("hello", "hello", 1.0, 1.4),
        ObservedWord("world", "world", 1.5, 1.9),
        ObservedWord("again", "again", 4.0, 4.5),
    ]

    report = build_report_from_evidence(
        source_text=source_text,
        source_kind="user_supplied",
        work_id=work_id,
        artifact_id=artifact_id,
        version_id=version_id,
        transcript=transcript,
        mapping={0: 0, 1: 1, 2: 2},
        score_word_pair=_score,
        normalize=_normalize,
        model_name="base",
        match_threshold=55.0,
        trusted_score=85.0,
    )

    assert report.source_text == source_text
    assert report.audio_provenance.version_id == version_id
    assert report.text_provenance.source_kind == "user_supplied"
    assert len(report.text_provenance.sha256) == 64
    assert report.method.parameters["use_lyrics_prompt"] is False
    assert report.method.parameters["interpolate_unmatched"] is False

    assert [word.status for word in report.words] == [
        "aligned",
        "ambiguous",
        "aligned",
        "failed",
    ]
    assert report.words[0].start_seconds == 1.0
    assert report.words[0].end_seconds == 1.4
    assert report.words[1].match_score == 80.0
    assert report.words[3].start_seconds is None
    assert report.words[3].end_seconds is None
    assert report.words[3].reason == "no_direct_match_above_threshold"

    assert [span.status for span in report.spans] == ["ambiguous", "ambiguous"]
    assert report.spans[0].start_seconds == 1.0
    assert report.spans[0].end_seconds == 1.9
    assert report.spans[1].start_seconds == 4.0
    assert report.spans[1].end_seconds == 4.5


def test_failed_span_never_receives_interpolated_timing():
    report = build_report_from_evidence(
        source_text="instrumental gap words",
        source_kind="licensed",
        work_id=UUID("00000000-0000-0000-0000-000000000011"),
        artifact_id=UUID("00000000-0000-0000-0000-000000000012"),
        version_id=UUID("00000000-0000-0000-0000-000000000013"),
        transcript=[],
        mapping={},
        score_word_pair=_score,
        normalize=_normalize,
        model_name="base",
        match_threshold=55.0,
        trusted_score=85.0,
    )

    assert all(word.status == "failed" for word in report.words)
    assert report.spans[0].status == "failed"
    assert report.spans[0].start_seconds is None
    assert report.spans[0].end_seconds is None

"""Focused truth-contract tests for supplied-text alignment."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from domain.lyrics_alignment_report import (
    LyricsAlignmentMethod,
    LyricsAlignmentReport,
    LyricsAlignmentRequest,
    LyricsWordSpan,
)


def _method() -> LyricsAlignmentMethod:
    return LyricsAlignmentMethod(torchaudio_version="2.6.0", torch_version="2.6.0")


def test_request_preserves_exact_user_text_and_requires_license_reference() -> None:
    text = "  First line\nsecond line  "
    request = LyricsAlignmentRequest(text=text, text_source="user_provided")
    assert request.text == text

    with pytest.raises(ValidationError, match="licensed text requires"):
        LyricsAlignmentRequest(text="licensed words", text_source="licensed")


def test_report_keeps_exact_provenance_and_local_ambiguous_failed_states() -> None:
    audio_version_id = uuid4()
    artifact_id = uuid4()
    report = LyricsAlignmentReport(
        source_audio_version_id=audio_version_id,
        source_audio_artifact_id=artifact_id,
        source_audio_sha256="a" * 64,
        source_text="clear maybe missing",
        source_text_sha256="b" * 64,
        text_source="user_provided",
        method=_method(),
        status="partial",
        spans=[
            LyricsWordSpan(
                index=0,
                text="clear",
                char_start=0,
                char_end=5,
                status="aligned",
                start_seconds=1.0,
                end_seconds=1.4,
                score=0.91,
            ),
            LyricsWordSpan(
                index=1,
                text="maybe",
                char_start=6,
                char_end=11,
                status="ambiguous",
                start_seconds=1.5,
                end_seconds=1.9,
                score=0.41,
                reason="low_ctc_alignment_score",
            ),
            LyricsWordSpan(
                index=2,
                text="missing",
                char_start=12,
                char_end=19,
                status="failed",
                reason="no_token_alignment",
            ),
        ],
    )

    assert report.source_audio_version_id == audio_version_id
    assert report.source_audio_artifact_id == artifact_id
    assert report.source_text == "clear maybe missing"
    assert report.method.role == "experimental_fallback"
    assert report.method.transcription_used is False
    assert [span.status for span in report.spans] == ["aligned", "ambiguous", "failed"]


def test_failed_span_cannot_fabricate_timing_or_score() -> None:
    with pytest.raises(ValidationError, match="failed spans must not fabricate"):
        LyricsWordSpan(
            index=0,
            text="word",
            char_start=0,
            char_end=4,
            status="failed",
            start_seconds=1.0,
            end_seconds=1.2,
            score=0.8,
            reason="failed",
        )


def test_failed_report_requires_failure_reason_and_no_timed_spans() -> None:
    with pytest.raises(ValidationError, match="failed reports require failure_reason"):
        LyricsAlignmentReport(
            source_audio_version_id=uuid4(),
            source_audio_artifact_id=uuid4(),
            source_audio_sha256="a" * 64,
            source_text="word",
            source_text_sha256="b" * 64,
            text_source="user_provided",
            method=_method(),
            status="failed",
            spans=[
                LyricsWordSpan(
                    index=0,
                    text="word",
                    char_start=0,
                    char_end=4,
                    status="failed",
                    reason="ctc_alignment_failed",
                )
            ],
        )

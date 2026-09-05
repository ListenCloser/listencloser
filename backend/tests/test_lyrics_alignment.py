"""Pure alignment adapter tests; no checkpoint download."""

import pytest

from lyrics_alignment import (
    LyricsAlignmentInputError,
    _TokenSpan,
    _source_words,
    _target_text,
    _word_spans_from_tokens,
)


def _labels() -> dict[str, int]:
    alphabet = "-|ABCDEFGHIJKLMNOPQRSTUVWXYZ'"
    return {character: index for index, character in enumerate(alphabet)}


def test_word_spans_preserve_source_offsets_and_mark_low_score_ambiguous() -> None:
    text = "Hi, there!"
    words = _source_words(text)
    labels = _labels()
    target = _target_text(words, labels)
    token_spans = [
        _TokenSpan(token=labels[character], start=index * 2, end=index * 2 + 1, score=score)
        for index, (character, score) in enumerate(
            zip(target, [0.9, 0.9, 0.9, 0.4, 0.4, 0.4, 0.4, 0.4], strict=True)
        )
    ]

    spans = _word_spans_from_tokens(
        words,
        target,
        token_spans,
        labels,
        seconds_per_frame=0.01,
        ambiguity_threshold=0.55,
    )

    assert [(span.text, span.char_start, span.char_end) for span in spans] == [
        ("Hi", 0, 2),
        ("there", 4, 9),
    ]
    assert spans[0].status == "aligned"
    assert spans[1].status == "ambiguous"
    assert spans[1].reason == "low_ctc_alignment_score"
    assert spans[0].start_seconds == 0.0
    assert spans[1].end_seconds == pytest.approx(0.15)


def test_english_fallback_rejects_unrepresentable_text_instead_of_normalizing_it() -> None:
    words = _source_words("café")
    with pytest.raises(LyricsAlignmentInputError, match="unsupported_characters"):
        _target_text(words, _labels())


def test_token_mismatch_is_not_silently_projected() -> None:
    words = _source_words("hi")
    labels = _labels()
    target = _target_text(words, labels)
    with pytest.raises(LyricsAlignmentInputError, match="token_mismatch"):
        _word_spans_from_tokens(
            words,
            target,
            [_TokenSpan(token=labels["H"], start=0, end=1, score=0.9)],
            labels,
            seconds_per_frame=0.01,
            ambiguity_threshold=0.55,
        )

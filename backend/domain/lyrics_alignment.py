"""Adapter from exact supplied text + audio to normalized alignment evidence."""

from __future__ import annotations

import hashlib
import importlib.metadata
import re
from dataclasses import dataclass
from pathlib import Path

from domain.lyrics_alignment_report import (
    AlignedTextSpan,
    AlignedWord,
    AlignmentMethod,
    AudioSourceProvenance,
    LyricsAlignmentReport,
    TextSourceProvenance,
)

SYNCALONG_RELEASE = "v2.0.1"
SYNCALONG_VERSION = "2.0.1"
OPENAI_WHISPER_VERSION = "20250625"
DEFAULT_MODEL = "base"
DEFAULT_MATCH_THRESHOLD = 55.0
DEFAULT_TRUSTED_SCORE = 85.0


@dataclass(frozen=True)
class ObservedWord:
    normalized: str
    raw: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class Token:
    index: int
    text: str
    char_start: int
    char_end: int
    normalized: str


def _tokenize(source_text: str, normalize) -> list[Token]:
    tokens: list[Token] = []
    for index, match in enumerate(re.finditer(r"\S+", source_text)):
        raw = match.group(0)
        tokens.append(
            Token(
                index=index,
                text=raw,
                char_start=match.start(),
                char_end=match.end(),
                normalized=normalize(raw),
            )
        )
    return tokens


def _line_ranges(source_text: str) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    cursor = 0
    for line in source_text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        start = cursor
        end = cursor + len(body)
        if body.strip():
            ranges.append((start, end, source_text[start:end]))
        cursor += len(line)
    return ranges


def build_report_from_evidence(
    *,
    source_text: str,
    source_kind: str,
    work_id,
    artifact_id,
    version_id,
    transcript: list[ObservedWord],
    mapping: dict[int, int],
    score_word_pair,
    normalize,
    model_name: str,
    match_threshold: float,
    trusted_score: float,
    engine_version: str = SYNCALONG_VERSION,
    whisper_version: str = OPENAI_WHISPER_VERSION,
) -> LyricsAlignmentReport:
    """Build the persisted truth contract without fabricating missing timing."""
    tokens = _tokenize(source_text, normalize)
    alignable = [token for token in tokens if token.normalized]
    alignable_to_token = [token.index for token in alignable]
    token_to_flat = {token_index: flat for flat, token_index in enumerate(alignable_to_token)}

    words: list[AlignedWord] = []
    for token in tokens:
        flat_index = token_to_flat.get(token.index)
        if flat_index is None:
            words.append(
                AlignedWord(
                    index=token.index,
                    text=token.text,
                    char_start=token.char_start,
                    char_end=token.char_end,
                    status="failed",
                    reason="token_normalizes_to_empty",
                )
            )
            continue

        transcript_index = mapping.get(flat_index)
        if transcript_index is None or not (0 <= transcript_index < len(transcript)):
            words.append(
                AlignedWord(
                    index=token.index,
                    text=token.text,
                    char_start=token.char_start,
                    char_end=token.char_end,
                    normalized_text=token.normalized,
                    status="failed",
                    reason="no_direct_match_above_threshold",
                )
            )
            continue

        observed = transcript[transcript_index]
        score = float(score_word_pair(token.normalized, observed.normalized))
        status = "aligned" if score >= trusted_score else "ambiguous"
        words.append(
            AlignedWord(
                index=token.index,
                text=token.text,
                char_start=token.char_start,
                char_end=token.char_end,
                normalized_text=token.normalized,
                status=status,
                start_seconds=float(observed.start_seconds),
                end_seconds=float(observed.end_seconds),
                match_score=score,
                reason=None if status == "aligned" else "direct_match_below_trusted_score",
            )
        )

    spans: list[AlignedTextSpan] = []
    for span_index, (char_start, char_end, text) in enumerate(_line_ranges(source_text)):
        span_words = [
            word for word in words if word.char_start >= char_start and word.char_end <= char_end
        ]
        if not span_words:
            continue
        timed = [word for word in span_words if word.start_seconds is not None]
        if not timed:
            status = "failed"
            reason = "no_direct_word_matches"
            start_seconds = None
            end_seconds = None
        elif all(word.status == "aligned" for word in span_words):
            status = "aligned"
            reason = None
            start_seconds = timed[0].start_seconds
            end_seconds = timed[-1].end_seconds
        else:
            status = "ambiguous"
            reason = "span_contains_ambiguous_or_failed_words"
            start_seconds = timed[0].start_seconds
            end_seconds = timed[-1].end_seconds

        spans.append(
            AlignedTextSpan(
                index=span_index,
                text=text,
                char_start=char_start,
                char_end=char_end,
                word_start_index=span_words[0].index,
                word_end_index=span_words[-1].index,
                status=status,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                reason=reason,
            )
        )

    return LyricsAlignmentReport(
        source_text=source_text,
        text_provenance=TextSourceProvenance(
            source_kind=source_kind,
            sha256=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            character_count=len(source_text),
        ),
        audio_provenance=AudioSourceProvenance(
            work_id=work_id,
            artifact_id=artifact_id,
            version_id=version_id,
        ),
        method=AlignmentMethod(
            engine_version=engine_version,
            engine_release=SYNCALONG_RELEASE,
            transcription_engine_version=whisper_version,
            model_name=model_name,
            parameters={
                "match_threshold": match_threshold,
                "trusted_score": trusted_score,
                "use_lyrics_prompt": False,
                "interpolate_unmatched": False,
                "separate_vocals": False,
            },
        ),
        words=words,
        spans=spans,
    )


def align_supplied_text(
    *,
    source_text: str,
    source_kind: str,
    audio_path: Path,
    work_id,
    artifact_id,
    version_id,
    model_name: str = DEFAULT_MODEL,
    language: str | None = None,
    match_threshold: float = DEFAULT_MATCH_THRESHOLD,
    trusted_score: float = DEFAULT_TRUSTED_SCORE,
) -> LyricsAlignmentReport:
    """Run the pinned syncalong matcher while preserving supplied text authority."""
    if not source_text.strip():
        raise ValueError("supplied text must not be empty")
    if trusted_score < match_threshold:
        raise ValueError("trusted score must be greater than or equal to match threshold")

    # Heavy/vendor imports remain behind this adapter boundary.
    from syncalong.align import _dp_align, _word_score
    from syncalong.textnorm import normalize
    from syncalong.transcribe import Transcriber

    transcriber = Transcriber(model_name)
    observed = transcriber.transcribe(
        audio_path,
        language=language,
        initial_prompt=None,
        separate_vocals=False,
    )
    transcript = [
        ObservedWord(
            normalized=word.word,
            raw=word.raw,
            start_seconds=float(word.start),
            end_seconds=float(word.end),
        )
        for word in observed
    ]
    tokens = _tokenize(source_text, normalize)
    lyric_words = [token.normalized for token in tokens if token.normalized]
    mapping = _dp_align(lyric_words, observed, match_threshold)

    try:
        whisper_version = importlib.metadata.version("openai-whisper")
    except importlib.metadata.PackageNotFoundError:
        whisper_version = OPENAI_WHISPER_VERSION

    return build_report_from_evidence(
        source_text=source_text,
        source_kind=source_kind,
        work_id=work_id,
        artifact_id=artifact_id,
        version_id=version_id,
        transcript=transcript,
        mapping=mapping,
        score_word_pair=_word_score,
        normalize=normalize,
        model_name=model_name,
        match_threshold=match_threshold,
        trusted_score=trusted_score,
        engine_version=importlib.metadata.version("syncalong"),
        whisper_version=whisper_version,
    )

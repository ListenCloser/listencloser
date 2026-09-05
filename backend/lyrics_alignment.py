"""Experimental supplied-text forced alignment using the pinned TorchAudio stack.

The acoustic model is speech-derived and English-only. This module never
transcribes audio: the caller's exact text is the sole target sequence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from uuid import UUID

import numpy as np

from domain.lyrics_alignment_report import (
    METHOD_ID,
    LyricsAlignmentMethod,
    LyricsAlignmentReport,
    LyricsWordSpan,
)
from perceptual_evidence import CANONICAL_SAMPLE_RATE, canonicalize_audio_bytes

_MODEL_SAMPLE_RATE = 16_000
_WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", flags=re.UNICODE)


class LyricsAlignmentInputError(ValueError):
    """The supplied text/audio pair cannot be represented by this fallback."""


@dataclass(frozen=True)
class _SourceWord:
    index: int
    text: str
    char_start: int
    char_end: int
    normalized: str


@dataclass(frozen=True)
class _TokenSpan:
    token: int
    start: int
    end: int
    score: float


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def _source_words(text: str) -> list[_SourceWord]:
    words: list[_SourceWord] = []
    for index, match in enumerate(_WORD_RE.finditer(text)):
        raw = match.group(0)
        words.append(
            _SourceWord(
                index=index,
                text=raw,
                char_start=match.start(),
                char_end=match.end(),
                normalized=raw.upper().replace("’", "'"),
            )
        )
    if not words:
        raise LyricsAlignmentInputError("no_alignable_words")
    return words


def _target_text(words: list[_SourceWord], label_to_id: dict[str, int]) -> str:
    unsupported = sorted(
        {
            character
            for word in words
            for character in word.normalized
            if character not in label_to_id
        }
    )
    if unsupported:
        raise LyricsAlignmentInputError(
            "unsupported_characters_for_english_fallback:"
            + ",".join(repr(character) for character in unsupported)
        )
    if "|" not in label_to_id:
        raise RuntimeError("TorchAudio English label set is missing word separator '|'")
    return "|".join(word.normalized for word in words)


def _word_ranges(words: list[_SourceWord]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for word in words:
        start = cursor
        end = start + len(word.normalized)
        ranges.append((start, end))
        cursor = end + 1
    return ranges


def _word_spans_from_tokens(
    words: list[_SourceWord],
    target_text: str,
    token_spans: list[_TokenSpan],
    label_to_id: dict[str, int],
    *,
    seconds_per_frame: float,
    ambiguity_threshold: float,
) -> list[LyricsWordSpan]:
    expected_ids = [label_to_id[character] for character in target_text]
    actual_ids = [span.token for span in token_spans]
    if actual_ids != expected_ids:
        raise LyricsAlignmentInputError("ctc_alignment_token_mismatch")

    result: list[LyricsWordSpan] = []
    for word, (start, end) in zip(words, _word_ranges(words), strict=True):
        evidence = token_spans[start:end]
        if not evidence:
            result.append(
                LyricsWordSpan(
                    index=word.index,
                    text=word.text,
                    char_start=word.char_start,
                    char_end=word.char_end,
                    status="failed",
                    reason="no_token_alignment",
                )
            )
            continue
        score = float(np.mean([span.score for span in evidence]))
        start_seconds = max(0.0, evidence[0].start * seconds_per_frame)
        end_seconds = max(start_seconds, evidence[-1].end * seconds_per_frame)
        if score < ambiguity_threshold:
            status = "ambiguous"
            reason = "low_ctc_alignment_score"
        else:
            status = "aligned"
            reason = None
        result.append(
            LyricsWordSpan(
                index=word.index,
                text=word.text,
                char_start=word.char_start,
                char_end=word.char_end,
                status=status,
                start_seconds=round(start_seconds, 4),
                end_seconds=round(end_seconds, 4),
                score=round(max(0.0, min(1.0, score)), 4),
                reason=reason,
            )
        )
    return result


def _method(*, ambiguity_threshold: float) -> LyricsAlignmentMethod:
    return LyricsAlignmentMethod(
        torchaudio_version=_package_version("torchaudio"),
        torch_version=_package_version("torch"),
        parameters={
            "model_sample_rate": _MODEL_SAMPLE_RATE,
            "source_decode_sample_rate": CANONICAL_SAMPLE_RATE,
            "ambiguity_threshold": ambiguity_threshold,
            "target_separator": "|",
        },
    )


def _failed_report(
    *,
    words: list[_SourceWord],
    source_text: str,
    source_text_sha256: str,
    text_source: str,
    text_source_reference: str | None,
    source_audio_version_id: UUID,
    source_audio_artifact_id: UUID,
    source_audio_sha256: str,
    ambiguity_threshold: float,
    reason: str,
) -> LyricsAlignmentReport:
    return LyricsAlignmentReport(
        source_audio_version_id=source_audio_version_id,
        source_audio_artifact_id=source_audio_artifact_id,
        source_audio_sha256=source_audio_sha256,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
        text_source=text_source,
        text_source_reference=text_source_reference,
        method=_method(ambiguity_threshold=ambiguity_threshold),
        status="failed",
        failure_reason=reason,
        spans=[
            LyricsWordSpan(
                index=word.index,
                text=word.text,
                char_start=word.char_start,
                char_end=word.char_end,
                status="failed",
                reason=reason,
            )
            for word in words
        ],
    )


def align_supplied_text_to_audio(
    audio_bytes: bytes,
    *,
    fmt: str,
    source_text: str,
    source_text_sha256: str,
    text_source: str,
    text_source_reference: str | None,
    source_audio_version_id: UUID,
    source_audio_artifact_id: UUID,
    source_audio_sha256: str,
    ambiguity_threshold: float,
) -> LyricsAlignmentReport:
    """Align the caller-provided English text to exact audio bytes.

    Operational/model-load failures are raised so the Job fails. Input/CTC
    insufficiency is persisted as an explicit failed report instead.
    """
    words = _source_words(source_text)

    # Lazy worker-only imports keep the API/core dependency surface unchanged.
    import torch
    import torchaudio

    bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
    labels = bundle.get_labels()
    label_to_id = {label: index for index, label in enumerate(labels)}
    try:
        target_text = _target_text(words, label_to_id)
    except LyricsAlignmentInputError as error:
        return _failed_report(
            words=words,
            source_text=source_text,
            source_text_sha256=source_text_sha256,
            text_source=text_source,
            text_source_reference=text_source_reference,
            source_audio_version_id=source_audio_version_id,
            source_audio_artifact_id=source_audio_artifact_id,
            source_audio_sha256=source_audio_sha256,
            ambiguity_threshold=ambiguity_threshold,
            reason=str(error),
        )

    samples = canonicalize_audio_bytes(audio_bytes, fmt=fmt)
    waveform = torch.from_numpy(samples).unsqueeze(0)
    if CANONICAL_SAMPLE_RATE != bundle.sample_rate:
        waveform = torchaudio.functional.resample(
            waveform,
            CANONICAL_SAMPLE_RATE,
            bundle.sample_rate,
        )

    model = bundle.get_model().eval()
    with torch.inference_mode():
        emissions, _ = model(waveform)
        log_probs = torch.log_softmax(emissions, dim=-1)

    targets = torch.tensor(
        [[label_to_id[character] for character in target_text]],
        dtype=torch.int32,
    )
    repeated = sum(
        left == right
        for left, right in zip(
            targets[0][:-1].tolist(), targets[0][1:].tolist(), strict=False
        )
    )
    if log_probs.shape[1] < targets.shape[1] + repeated:
        return _failed_report(
            words=words,
            source_text=source_text,
            source_text_sha256=source_text_sha256,
            text_source=text_source,
            text_source_reference=text_source_reference,
            source_audio_version_id=source_audio_version_id,
            source_audio_artifact_id=source_audio_artifact_id,
            source_audio_sha256=source_audio_sha256,
            ambiguity_threshold=ambiguity_threshold,
            reason="text_too_long_for_audio_ctc_alignment",
        )

    try:
        aligned_tokens, alignment_scores = torchaudio.functional.forced_align(
            log_probs,
            targets,
            blank=0,
        )
        merged = torchaudio.functional.merge_tokens(
            aligned_tokens[0],
            alignment_scores[0].exp(),
            blank=0,
        )
        token_spans = [
            _TokenSpan(
                token=int(span.token),
                start=int(span.start),
                end=int(span.end),
                score=float(span.score),
            )
            for span in merged
        ]
        seconds_per_frame = waveform.shape[-1] / bundle.sample_rate / max(
            1, log_probs.shape[1]
        )
        spans = _word_spans_from_tokens(
            words,
            target_text,
            token_spans,
            label_to_id,
            seconds_per_frame=seconds_per_frame,
            ambiguity_threshold=ambiguity_threshold,
        )
    except (LyricsAlignmentInputError, RuntimeError) as error:
        return _failed_report(
            words=words,
            source_text=source_text,
            source_text_sha256=source_text_sha256,
            text_source=text_source,
            text_source_reference=text_source_reference,
            source_audio_version_id=source_audio_version_id,
            source_audio_artifact_id=source_audio_artifact_id,
            source_audio_sha256=source_audio_sha256,
            ambiguity_threshold=ambiguity_threshold,
            reason=f"ctc_alignment_failed:{type(error).__name__}",
        )

    has_ambiguous = any(span.status == "ambiguous" for span in spans)
    has_failed = any(span.status == "failed" for span in spans)
    status = "partial" if has_ambiguous or has_failed else "complete"
    return LyricsAlignmentReport(
        source_audio_version_id=source_audio_version_id,
        source_audio_artifact_id=source_audio_artifact_id,
        source_audio_sha256=source_audio_sha256,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
        text_source=text_source,
        text_source_reference=text_source_reference,
        method=_method(ambiguity_threshold=ambiguity_threshold),
        status=status,
        spans=spans,
    )


__all__ = [
    "METHOD_ID",
    "LyricsAlignmentInputError",
    "align_supplied_text_to_audio",
]

"""Persisted contract for experimental supplied-text alignment."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

REPORT_SCHEMA_VERSION = 1
METHOD_ID = "syncalong_dp_whisper_v1"


class TextSourceProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_kind: Literal["user_supplied", "licensed", "public_domain", "other_permitted"]
    sha256: str
    character_count: int
    rights_assertion: str = (
        "The text was supplied under a user-declared permitted source; "
        "alignment does not change text ownership or rights."
    )


class AudioSourceProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_id: UUID
    artifact_id: UUID
    version_id: UUID


class AlignmentMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Literal["syncalong_dp_whisper_v1"] = METHOD_ID
    engine: Literal["syncalong"] = "syncalong"
    engine_version: str
    engine_release: str
    engine_license: Literal["MIT"] = "MIT"
    transcription_engine: Literal["openai-whisper"] = "openai-whisper"
    transcription_engine_version: str
    transcription_license: Literal["MIT"] = "MIT"
    model_name: str
    model_license: Literal["MIT"] = "MIT"
    parameters: dict[str, float | int | str | bool | None]


class AlignedWord(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    text: str
    char_start: int
    char_end: int
    normalized_text: str | None = None
    status: Literal["aligned", "ambiguous", "failed"]
    start_seconds: float | None = None
    end_seconds: float | None = None
    match_score: float | None = Field(default=None, ge=0.0, le=100.0)
    reason: str | None = None


class AlignedTextSpan(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    text: str
    char_start: int
    char_end: int
    word_start_index: int
    word_end_index: int
    status: Literal["aligned", "ambiguous", "failed"]
    start_seconds: float | None = None
    end_seconds: float | None = None
    reason: str | None = None


class LyricsAlignmentReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = REPORT_SCHEMA_VERSION
    report_type: Literal["supplied_text_alignment"] = "supplied_text_alignment"
    experimental: Literal[True] = True
    source_text: str
    text_provenance: TextSourceProvenance
    audio_provenance: AudioSourceProvenance
    method: AlignmentMethod
    words: list[AlignedWord]
    spans: list[AlignedTextSpan]
    interpretation: str = (
        "Timestamps are method-specific associations between supplied text tokens and "
        "word-level audio evidence. They do not prove the singer used the exact supplied wording."
    )
    limitations: list[str] = Field(
        default_factory=lambda: [
            (
                "Unmatched tokens remain failed; no timestamp interpolation or "
                "extrapolation is used."
            ),
            (
                "Lower-similarity direct matches are marked ambiguous instead of "
                "confidence-styled away."
            ),
            (
                "Melisma, backing vocals, ad-libs, repeated words, pronunciation changes, "
                "and dense mixtures can weaken or defeat alignment."
            ),
            "This report does not create beat, pulse, section, or transcript authority.",
        ]
    )

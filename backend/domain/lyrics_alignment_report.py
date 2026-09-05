"""Truth contract for supplied-text audio alignment reports."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REPORT_SCHEMA_VERSION = "1.0"
METHOD_ID = "torchaudio_wav2vec2_ctc_forced_align_en_v1"

TextSourceKind = Literal["user_provided", "licensed"]
AlignmentSpanStatus = Literal["aligned", "ambiguous", "failed"]
AlignmentOverallStatus = Literal["complete", "partial", "failed"]


class LyricsAlignmentRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=50_000)
    text_source: TextSourceKind
    text_source_reference: str | None = Field(default=None, max_length=500)
    language: Literal["en"] = "en"
    ambiguity_threshold: float = Field(default=0.55, ge=0.0, le=1.0)

    @field_validator("text")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain at least one non-whitespace character")
        return value

    @model_validator(mode="after")
    def _licensed_text_has_reference(self) -> "LyricsAlignmentRequest":
        if self.text_source == "licensed" and not (self.text_source_reference or "").strip():
            raise ValueError("licensed text requires text_source_reference")
        return self


class LyricsAlignmentMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Literal["torchaudio_wav2vec2_ctc_forced_align_en_v1"] = METHOD_ID
    torchaudio_version: str
    torch_version: str
    implementation: Literal["torchaudio.functional.forced_align"] = (
        "torchaudio.functional.forced_align"
    )
    implementation_license: Literal["BSD-2-Clause"] = "BSD-2-Clause"
    model_bundle: Literal["WAV2VEC2_ASR_BASE_960H"] = "WAV2VEC2_ASR_BASE_960H"
    checkpoint: Literal["wav2vec2_fairseq_base_ls960_asr_ls960.pth"] = (
        "wav2vec2_fairseq_base_ls960_asr_ls960.pth"
    )
    model_license: Literal["MIT"] = "MIT"
    trained_domain: Literal["English speech (LibriSpeech)"] = "English speech (LibriSpeech)"
    role: Literal["experimental_fallback"] = "experimental_fallback"
    transcription_used: Literal[False] = False
    parameters: dict[str, float | int | str] = Field(default_factory=dict)


class LyricsWordSpan(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    status: AlignmentSpanStatus
    start_seconds: float | None = Field(default=None, ge=0.0)
    end_seconds: float | None = Field(default=None, ge=0.0)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str | None = None

    @model_validator(mode="after")
    def _state_is_explicit(self) -> "LyricsWordSpan":
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if self.status in {"aligned", "ambiguous"}:
            if self.start_seconds is None or self.end_seconds is None or self.score is None:
                raise ValueError("timed spans require start_seconds, end_seconds, and score")
            if self.end_seconds < self.start_seconds:
                raise ValueError("end_seconds must not precede start_seconds")
        if self.status == "aligned" and self.reason is not None:
            raise ValueError("aligned spans must not carry a failure/ambiguity reason")
        if self.status == "ambiguous" and not self.reason:
            raise ValueError("ambiguous spans require a reason")
        if self.status == "failed":
            if self.start_seconds is not None or self.end_seconds is not None or self.score is not None:
                raise ValueError("failed spans must not fabricate timing or score")
            if not self.reason:
                raise ValueError("failed spans require a reason")
        return self


class LyricsAlignmentReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = REPORT_SCHEMA_VERSION
    experimental: Literal[True] = True
    source_audio_version_id: UUID
    source_audio_artifact_id: UUID
    source_audio_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_text: str
    source_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_source: TextSourceKind
    text_source_reference: str | None = None
    language: Literal["en"] = "en"
    granularity: Literal["word"] = "word"
    method: LyricsAlignmentMethod
    status: AlignmentOverallStatus
    spans: list[LyricsWordSpan] = Field(default_factory=list)
    failure_reason: str | None = None

    @model_validator(mode="after")
    def _aggregate_state_is_truthful(self) -> "LyricsAlignmentReport":
        timed = [span for span in self.spans if span.status != "failed"]
        failed = [span for span in self.spans if span.status == "failed"]
        ambiguous = [span for span in self.spans if span.status == "ambiguous"]
        if self.status == "complete" and (failed or ambiguous or not self.spans):
            raise ValueError("complete reports require only aligned spans")
        if self.status == "partial" and (not timed or not (failed or ambiguous)):
            raise ValueError("partial reports require timed and non-aligned evidence")
        if self.status == "failed":
            if timed:
                raise ValueError("failed reports must not contain timed spans")
            if not self.failure_reason:
                raise ValueError("failed reports require failure_reason")
        elif self.failure_reason is not None:
            raise ValueError("non-failed reports must not carry failure_reason")
        return self

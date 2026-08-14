"""Pydantic contract for the grounded contextual Ask endpoint.

These models mirror the TypeScript `AskContext` / `AskReference` /
`AskAction` / `AskResponse` types defined in `lib/ask/types.ts` (merged via
#226/#227). The backend is the consumer side of that contract: it accepts the
derived context the frontend sends and returns a schema-valid `AskResponse`.

Every field is bounded so a single request cannot carry an arbitrary giant
prompt payload. Invalid references/actions are handled by the deterministic
sanitization layer (`ask.sanitize`), not by silently accepting model output.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

QUESTION_MAX_LENGTH = 2000
MAX_VISIBLE_INSIGHTS = 100
MAX_REFERENCES = 12
MAX_SUGGESTED_ACTIONS = 8
MAX_NOTES_PER_REFERENCE = 64
MAX_NOTE_ID_LENGTH = 128
MAX_CLAIM_LENGTH = 2000
MIN_MEASURE = 1

# ---------------------------------------------------------------------------
# AskContext (request)
# ---------------------------------------------------------------------------


class AskSelectionTimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float = Field(ge=0)
    end: float = Field(ge=0)
    domain: Literal["performance", "notation"]


class AskSelectionMeasureRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int
    end: int


class AskSelectionProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Literal["waveform", "piano_roll", "score", None]
    timeExact: bool
    measureApproximate: bool


class AskSelection(BaseModel):
    """Mirror of the frontend `MusicalSelection` (all fields optional)."""

    model_config = ConfigDict(extra="forbid")

    timeRange: AskSelectionTimeRange | None = None
    noteIds: list[Annotated[str, Field(max_length=MAX_NOTE_ID_LENGTH)]] | None = None
    measureRange: AskSelectionMeasureRange | None = None
    provenance: AskSelectionProvenance | None = None


class AskInsightSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_seconds: float | None = None
    end_seconds: float | None = None
    start_beat: float | None = None
    end_beat: float | None = None
    start_measure: int | None = None
    end_measure: int | None = None


class AskInsight(BaseModel):
    """The subset of an `Insight` the explainer needs.

    The frontend sends the full insight object; unknown extra fields (created_at,
    evidence, provenance, confidence, ...) are tolerated but not surfaced to the
    model, so no arbitrary database rows leak into the prompt.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    version_id: str
    kind: str
    claim: Annotated[str, Field(max_length=MAX_CLAIM_LENGTH)]
    span: AskInsightSpan = Field(default_factory=AskInsightSpan)
    entity_ids: list[str] = Field(default_factory=list)


class AskVisibleInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insight: AskInsight
    category: Literal["selection", "whole-work"]


class AskContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workId: UUID
    representationId: Literal["listen", "piano_roll", "score"]
    currentTime: float = Field(ge=0, default=0.0)
    playbackSourceId: str | None = None
    selection: AskSelection | None = None
    visibleInsights: list[AskVisibleInsight] = Field(
        default_factory=list, max_length=MAX_VISIBLE_INSIGHTS
    )


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Annotated[str, Field(min_length=1, max_length=QUESTION_MAX_LENGTH)]
    context: AskContext


# ---------------------------------------------------------------------------
# AskResponse (model output / response)
# ---------------------------------------------------------------------------


class AskTimeReference(BaseModel):
    type: Literal["time"] = "time"
    start: float
    end: float | None = None
    domain: Literal["performance", "notation"]


class AskMeasureReference(BaseModel):
    type: Literal["measure"] = "measure"
    start: int
    end: int | None = None


class AskNotesReference(BaseModel):
    type: Literal["notes"] = "notes"
    ids: list[Annotated[str, Field(max_length=MAX_NOTE_ID_LENGTH)]] = Field(
        max_length=MAX_NOTES_PER_REFERENCE
    )


class AskInsightReference(BaseModel):
    type: Literal["insight"] = "insight"
    id: str


AskReference = Annotated[
    AskTimeReference | AskMeasureReference | AskNotesReference | AskInsightReference,
    Field(discriminator="type"),
]


class AskSeekAction(BaseModel):
    type: Literal["seek"] = "seek"
    seconds: float
    domain: Literal["performance", "notation"]


class AskLoopAction(BaseModel):
    type: Literal["loop"] = "loop"
    start: float
    end: float
    domain: Literal["performance", "notation"]


class AskShowRepresentationAction(BaseModel):
    type: Literal["show_representation"] = "show_representation"
    representationId: str


AskAction = Annotated[
    AskSeekAction | AskLoopAction | AskShowRepresentationAction,
    Field(discriminator="type"),
]


class AskResponse(BaseModel):
    answer: Annotated[str, Field(min_length=1, max_length=MAX_CLAIM_LENGTH)]
    references: list[AskReference] = Field(default_factory=list, max_length=MAX_REFERENCES)
    suggestedActions: list[AskAction] | None = Field(
        default_factory=list, max_length=MAX_SUGGESTED_ACTIONS
    )
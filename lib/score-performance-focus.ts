import {
  matchPerformanceEventsToPianoRollNoteIds,
  type AlignmentPerformanceEventIdentity,
  type PianoRollEntityNote,
} from "@/lib/performance-note-identity";
import {
  matchRenderedScoreNoteEvent,
  type AlignmentScoreEventIdentity,
  type RenderedScoreNoteIdentity,
} from "@/lib/score-note-identity";

export type ScorePerformanceRelation = {
  kind: "matched" | "score_only" | "performance_only" | "grouped";
  score_events: Array<{ event_id: string }>;
  performance_events: Array<{ event_id: string }>;
};

export type ScorePerformanceAlignmentReport = {
  score_version_id: string;
  performance_version_id: string;
  sufficiency: "sufficient" | "insufficient" | "failed";
  projection_precision: "adequate" | "unsupported";
  method: {
    package: string;
    package_version: string;
    matcher: string;
    parameters?: Record<string, unknown>;
  };
  relations: ScorePerformanceRelation[];
  event_identity: {
    schema_version: number;
    score_events: AlignmentScoreEventIdentity[];
    performance_events: AlignmentPerformanceEventIdentity[];
  };
};

export type ScorePerformanceFocusResolution = {
  scoreEventId: string;
  performanceEventIds: string[];
  pianoRollNoteIds: string[];
};

/**
 * Resolve one rendered Score note through the exact durable relation onto the
 * currently displayed canonical Piano Roll note world.
 *
 * Every boundary fails closed. This function never infers authority from
 * recency, never crosses to a different MIDI interpretation, and never chooses
 * a nearest relation or note.
 */
export function resolveScorePerformanceFocus(
  rendered: RenderedScoreNoteIdentity,
  report: ScorePerformanceAlignmentReport | null | undefined,
  displayedScoreVersionId: string | null | undefined,
  displayedPianoRollVersionId: string | null | undefined,
  pianoRollNotes: readonly PianoRollEntityNote[],
): ScorePerformanceFocusResolution | null {
  if (!report) return null;
  if (report.sufficiency !== "sufficient" || report.projection_precision !== "adequate") {
    return null;
  }
  if (
    !displayedScoreVersionId
    || !displayedPianoRollVersionId
    || report.score_version_id !== displayedScoreVersionId
    || report.performance_version_id !== displayedPianoRollVersionId
  ) {
    return null;
  }

  const scoreEvent = matchRenderedScoreNoteEvent(
    rendered,
    report.event_identity.score_events,
  );
  if (!scoreEvent) return null;

  const relations = report.relations.filter((relation) =>
    relation.score_events.some((event) => event.event_id === scoreEvent.event_id),
  );
  if (relations.length !== 1) return null;
  const relation = relations[0];
  if (relation.kind !== "matched" && relation.kind !== "grouped") return null;
  if (relation.performance_events.length === 0) return null;

  const performanceIdentityById = new Map(
    report.event_identity.performance_events.map((event) => [event.event_id, event]),
  );
  const performanceEvents: AlignmentPerformanceEventIdentity[] = [];
  for (const relationEvent of relation.performance_events) {
    const identity = performanceIdentityById.get(relationEvent.event_id);
    if (!identity) return null;
    performanceEvents.push(identity);
  }
  if (new Set(performanceEvents.map((event) => event.event_id)).size !== performanceEvents.length) {
    return null;
  }

  const pianoRollNoteIds = matchPerformanceEventsToPianoRollNoteIds(
    performanceEvents,
    pianoRollNotes,
  );
  if (!pianoRollNoteIds?.length) return null;

  return {
    scoreEventId: scoreEvent.event_id,
    performanceEventIds: performanceEvents.map((event) => event.event_id),
    pianoRollNoteIds,
  };
}

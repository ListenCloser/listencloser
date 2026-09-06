import type { Insight } from "@/lib/domain.types";
import type { PlaybackSource } from "@/lib/stores/transport";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { RepresentationId } from "@/lib/representations";
import { categorizeInsights } from "@/lib/inspector/insights";
import { isAskExposed } from "@/lib/inspector/capabilities";
import type { AskContext } from "./types";

export type { AskAction, AskContext, AskReference, AskResponse } from "./types";

function compactAskInsight(insight: Insight): Insight {
  if (insight.kind !== "rhythm") return insight;
  const evidence = insight.evidence ?? {};
  if (!("beats_seconds" in evidence) && !("downbeats_seconds" in evidence)) return insight;
  const {
    beats_seconds: _beatsSeconds,
    downbeats_seconds: _downbeatsSeconds,
    ...askEvidence
  } = evidence;
  return { ...insight, evidence: askEvidence };
}

/**
 * Derive the AskContext for the current workspace from existing
 * workspace/transport state. Pure function — no new authoritative state, no
 * side effects, no LLM call.
 *
 * Returns null until a work is loaded. `visibleInsights` is categorized via
 * the shared `categorizeInsights` helper so whole-work findings remain
 * distinguishable from selection-scoped findings; `unrelated` insights and
 * capabilities the backend registry marks `ask: false` are excluded.
 *
 * Representation-only pulse coordinate arrays are removed from the Ask copy of
 * a rhythm insight. The model still receives the compact rhythm measurements
 * and their provenance, while dense beat/downbeat timestamps stay available to
 * deterministic representation code through workspace insights.
 */
export function deriveAskContext(
  workId: string | null,
  representationId: RepresentationId | null,
  currentTime: number,
  activeSource: PlaybackSource | null,
  selection: MusicalSelection | null,
  insights: Insight[],
  bpm: number,
): AskContext | null {
  if (!workId) return null;
  const askExposedInsights = insights
    .filter((insight) => isAskExposed(insight.kind))
    .map(compactAskInsight);
  return {
    workId,
    representationId: representationId ?? "listen",
    currentTime,
    playbackSourceId: activeSource?.id ?? null,
    selection,
    visibleInsights: categorizeInsights(askExposedInsights, selection, bpm).filter(
      (item) => item.category === "selection" || item.category === "whole-work",
    ),
  };
}

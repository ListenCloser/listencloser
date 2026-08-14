import type { Insight } from "@/lib/domain.types";
import type { PlaybackSource } from "@/lib/stores/transport";
import type { MusicalSelection } from "@/lib/stores/workspace";
import { categorizeInsights } from "@/lib/inspector/insights";
import type { AskContext } from "./types";

export type { AskAction, AskContext, AskReference, AskResponse } from "./types";

/**
 * Derive the AskContext for the current workspace from existing
 * workspace/transport state. Pure function — no new authoritative state, no
 * side effects, no LLM call.
 *
 * Returns null until a work is loaded. `visibleInsights` is categorized via
 * the shared `categorizeInsights` helper so whole-work findings remain
 * distinguishable from selection-scoped findings; `unrelated` insights are
 * excluded to match what the workspace actually presents.
 */
export function deriveAskContext(
  workId: string | null,
  representationId: string | null,
  currentTime: number,
  activeSource: PlaybackSource | null,
  selection: MusicalSelection | null,
  insights: Insight[],
  bpm: number,
): AskContext | null {
  if (!workId) return null;
  return {
    workId,
    representationId: representationId ?? "listen",
    currentTime,
    playbackSourceId: activeSource?.id ?? null,
    selection,
    visibleInsights: categorizeInsights(insights, selection, bpm).filter(
      (item) => item.category === "selection" || item.category === "whole-work",
    ),
  };
}

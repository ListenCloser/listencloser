import type { Insight } from "@/lib/domain.types";
import type { MusicalSelection } from "@/lib/stores/workspace";

export type InsightCategory = "selection" | "whole-work" | "unrelated";

export interface CategorizedInsight {
  insight: Insight;
  category: InsightCategory;
}

/**
 * Derive a defensible start position (seconds) for an insight's temporal
 * location. Prefers `start_seconds`; falls back to a beat→time conversion
 * from `start_beat` when a valid BPM is available. Returns null when there is
 * no defensible temporal location — callers must NOT present such insights as
 * seekable buttons that jump to the beginning.
 */
export function insightStartSeconds(
  insight: Insight,
  bpm: number,
): number | null {
  const startSeconds = insight.span.start_seconds;
  if (typeof startSeconds === "number" && Number.isFinite(startSeconds)) {
    return startSeconds;
  }
  const startBeat = insight.span.start_beat;
  if (typeof startBeat === "number" && Number.isFinite(startBeat) && bpm > 0) {
    return startBeat * 60 / bpm;
  }
  return null;
}

export function categorizeInsights(
  insights: Insight[],
  selection: MusicalSelection | null,
  _bpm: number,
): CategorizedInsight[] {
  return insights.map((insight) => {
    const category = categorizeInsight(insight, selection);
    return { insight, category };
  });
}

function categorizeInsight(insight: Insight, selection: MusicalSelection | null): InsightCategory {
  if (!selection) return "whole-work";
  const selStart = selection.timeRange?.start ?? null;
  const selEnd = selection.timeRange?.end ?? null;
  if (selStart === null || selEnd === null) {
    return "whole-work";
  }
  const insightStart = insight.span.start_seconds;
  const insightEnd = insight.span.end_seconds;
  if (insightStart === null || insightEnd === null) {
    return "whole-work";
  }
  const overlaps = insightStart < selEnd && insightEnd > selStart;
  return overlaps ? "selection" : "unrelated";
}

export function filterByCategory(
  categorized: CategorizedInsight[],
  category: InsightCategory,
): Insight[] {
  return categorized.filter((c) => c.category === category).map((c) => c.insight);
}

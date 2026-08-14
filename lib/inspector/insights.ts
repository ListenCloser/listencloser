import type { Insight } from "@/lib/domain.types";
import type { MusicalSelection } from "@/lib/stores/workspace";

export type InsightCategory = "selection" | "whole-work" | "unrelated";

export interface CategorizedInsight {
  insight: Insight;
  category: InsightCategory;
}

export function categorizeInsights(
  insights: Insight[],
  selection: MusicalSelection | null,
  bpm: number,
): CategorizedInsight[] {
  return insights.map((insight) => {
    const category = categorizeInsight(insight, selection, bpm);
    return { insight, category };
  });
}

function categorizeInsight(insight: Insight, selection: MusicalSelection | null, bpm: number): InsightCategory {
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

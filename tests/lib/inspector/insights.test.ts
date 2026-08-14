import type { Insight } from "@/lib/domain.types";
import type { MusicalSelection } from "@/lib/stores/workspace";
import { categorizeInsights, filterByCategory, insightStartSeconds } from "@/lib/inspector/insights";
import { describe, expect, it } from "vitest";

function insight(overrides: Partial<Insight>): Insight {
  return {
    id: overrides.id ?? "insight-1",
    version_id: "version-1",
    kind: overrides.kind ?? "key",
    claim: overrides.claim ?? "Key: C major",
    span: overrides.span ?? { start_seconds: null, end_seconds: null, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
    entity_ids: [],
    evidence: overrides.evidence ?? {},
    confidence: overrides.confidence ?? null,
    provenance: overrides.provenance ?? {},
    created_at: new Date().toISOString(),
    created_by: null,
    produced_by_job_id: null,
  };
}

function timeSpan(start: number, end: number): NonNullable<Insight["span"]> {
  return { start_seconds: start, end_seconds: end, start_beat: null, end_beat: null, start_measure: null, end_measure: null };
}

describe("categorizeInsights", () => {
  const keyInsight = insight({ id: "key-1", kind: "key", confidence: 0.9, span: timeSpan(10, 20) });
  const tempoInsight = insight({ id: "tempo-1", kind: "tempo", confidence: 0.9, span: timeSpan(30, 40) });
  const unrelatedInsight = insight({ id: "chord-1", kind: "chord", confidence: 0.8, span: timeSpan(100, 120) });

  describe("default scope with/without selection", () => {
    it("categorizies as whole-work when there is no selection", () => {
      const result = categorizeInsights([keyInsight, tempoInsight], null, 120);
      expect(filterByCategory(result, "whole-work")).toHaveLength(2);
      expect(filterByCategory(result, "selection")).toHaveLength(0);
    });

    it("categorizies insights within selection time range as selection", () => {
      const selection: MusicalSelection = {
        timeRange: { start: 5, end: 25, domain: "performance" },
        provenance: { origin: null, timeExact: true, measureApproximate: false },
      };
      const result = categorizeInsights([keyInsight, tempoInsight], selection, 120);
      expect(filterByCategory(result, "selection")).toHaveLength(1);
      expect(filterByCategory(result, "selection")[0].id).toBe("key-1");
      expect(filterByCategory(result, "whole-work")).toHaveLength(0);
    });
  });

  describe("selection/insight overlap", () => {
    it("categorizies partially overlapping insights as selection", () => {
      const selection: MusicalSelection = {
        timeRange: { start: 15, end: 35, domain: "performance" },
        provenance: { origin: null, timeExact: true, measureApproximate: false },
      };
      const result = categorizeInsights([keyInsight, tempoInsight], selection, 120);
      expect(filterByCategory(result, "selection")).toHaveLength(2);
    });

    it("categorizies non-overlapping insights as unrelated", () => {
      const selection: MusicalSelection = {
        timeRange: { start: 5, end: 25, domain: "performance" },
        provenance: { origin: null, timeExact: true, measureApproximate: false },
      };
      const result = categorizeInsights([keyInsight, unrelatedInsight], selection, 120);
      expect(filterByCategory(result, "selection")).toHaveLength(1);
      expect(filterByCategory(result, "unrelated")).toHaveLength(1);
    });
  });

  describe("whole-piece insight categorization", () => {
    it("categorizies insights with null timestamps as whole-work", () => {
      const noTimestamp = insight({ id: "no-ts", kind: "key", confidence: 0.9 });
      const result = categorizeInsights([noTimestamp], null, 120);
      expect(filterByCategory(result, "whole-work")).toHaveLength(1);
    });

    it("categorizies insights with null timestamps as whole-work even when selection exists", () => {
      const noTimestamp = insight({ id: "no-ts", kind: "key", confidence: 0.9 });
      const selection: MusicalSelection = {
        timeRange: { start: 5, end: 25, domain: "performance" },
        provenance: { origin: null, timeExact: true, measureApproximate: false },
      };
      const result = categorizeInsights([noTimestamp], selection, 120);
      expect(filterByCategory(result, "whole-work")).toHaveLength(1);
    });
  });
});

describe("insightStartSeconds", () => {
  it("returns start_seconds directly when available", () => {
    const item = insight({ span: { start_seconds: 12.5, end_seconds: 20, start_beat: 48, end_beat: 80, start_measure: null, end_measure: null } });
    expect(insightStartSeconds(item, 120)).toBe(12.5);
  });

  it("derives seconds from start_beat when start_seconds is null and BPM is valid", () => {
    const item = insight({ span: { start_seconds: null, end_seconds: null, start_beat: 96, end_beat: 128, start_measure: null, end_measure: null } });
    // 96 beats at 120 BPM = 96 * 60 / 120 = 48 seconds
    expect(insightStartSeconds(item, 120)).toBe(48);
  });

  it("returns null when neither seconds nor beat-derived time exists", () => {
    const item = insight({ span: { start_seconds: null, end_seconds: null, start_beat: null, end_beat: null, start_measure: null, end_measure: null } });
    expect(insightStartSeconds(item, 120)).toBeNull();
  });

  it("returns null when BPM is not valid even if start_beat exists", () => {
    const item = insight({ span: { start_seconds: null, end_seconds: null, start_beat: 96, end_beat: 128, start_measure: null, end_measure: null } });
    expect(insightStartSeconds(item, 0)).toBeNull();
  });
});

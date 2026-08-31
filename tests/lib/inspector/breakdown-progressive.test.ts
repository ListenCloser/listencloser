import { describe, expect, it } from "vitest";
import { rankBreakdownFindings } from "@/lib/inspector/breakdown";
import type { TemporalFinding } from "@/lib/inspector/findings";

function finding(kind: TemporalFinding["kind"], evidence: Record<string, unknown> = {}): TemporalFinding {
  return {
    id: `finding-${kind}`,
    sourceInsightId: `insight-${kind}`,
    supportInsightIds: [`insight-${kind}`],
    kind,
    category: kind === "harmonic_activity" ? "harmony" : "rhythm",
    startSeconds: 10,
    endSeconds: 12,
    label: `Observed ${kind}`,
    evidence,
  } as TemporalFinding;
}

describe("progressive Breakdown copy", () => {
  it("does not paraphrase density headlines with a redundant support sentence", () => {
    const [peak] = rankBreakdownFindings([finding("density_peak", { density: 12 })]);
    const [valley] = rankBreakdownFindings([finding("density_valley", { density: 2 })]);

    expect(peak.headline).toContain("densest");
    expect(peak.evidenceSummary).toBe("");
    expect(valley.headline).toContain("sparse");
    expect(valley.evidenceSummary).toBe("");
  });

  it("keeps support copy when it adds magnitude or an interpretation boundary", () => {
    const [rest] = rankBreakdownFindings([finding("rest", { duration: 2.4 })]);
    const [harmony] = rankBreakdownFindings([finding("harmonic_activity", { chordDensity: 1.8 })]);

    expect(rest.evidenceSummary).toContain("2.4s");
    expect(harmony.evidenceSummary).toContain("not harmonic tension");
  });
});

import { describe, expect, it } from "vitest";
import { rankBreakdownFindings } from "@/lib/inspector/breakdown";
import type { TemporalFinding } from "@/lib/inspector/findings";

describe("Breakdown action truthfulness", () => {
  it("only guarantees focus before live workspace capabilities are checked", () => {
    const finding: TemporalFinding = {
      id: "density-peak",
      sourceInsightId: "density-source",
      supportInsightIds: ["density-source"],
      kind: "density_peak",
      category: "rhythm",
      startSeconds: 12,
      endSeconds: 15,
      label: "Peak note density around 0:12",
      evidence: { density: 9 },
    };

    const [breakdown] = rankBreakdownFindings([finding]);

    expect(breakdown.availableActions).toEqual(["focus"]);
    expect(breakdown.supportInsightIds).toEqual(["density-source"]);
  });
});

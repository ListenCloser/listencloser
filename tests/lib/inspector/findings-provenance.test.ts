import { describe, expect, it } from "vitest";
import { deriveFindings } from "@/lib/inspector/findings";
import type { Insight } from "@/lib/domain.types";

function span(start: number, end: number): Insight["span"] {
  return {
    start_seconds: start,
    end_seconds: end,
    start_beat: null,
    end_beat: null,
    start_measure: null,
    end_measure: null,
  };
}

function chord(id: string, start: number, end: number): Insight {
  return {
    id,
    version_id: "version-1",
    kind: "chord",
    claim: `Chord ${id}`,
    span: span(start, end),
    entity_ids: [],
    evidence: {},
    confidence: null,
    provenance: {},
    created_at: "2026-08-29T00:00:00Z",
    created_by: null,
    produced_by_job_id: null,
  };
}

describe("temporal finding support provenance", () => {
  it("attributes harmonic activity to the exact winning chord window", () => {
    const findings = deriveFindings([
      chord("c1", 0, 4),
      chord("c2", 4, 8),
      chord("c3", 8, 12),
      chord("c4", 20, 20.5),
      chord("c5", 20.5, 21),
      chord("c6", 21, 21.5),
    ]);

    const activity = findings.find((finding) => finding.kind === "harmonic_activity");

    expect(activity).toBeDefined();
    expect(activity?.startSeconds).toBe(20);
    expect(activity?.endSeconds).toBe(21.5);
    expect(activity?.sourceInsightId).toBe("c4");
    expect(activity?.supportInsightIds).toEqual(["c4", "c5", "c6"]);
    expect(activity?.supportInsightIds).not.toContain("c1");
  });
});

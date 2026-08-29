import { describe, expect, it } from "vitest";
import { deriveFindings } from "@/lib/inspector/findings";
import type { Insight } from "@/lib/domain.types";

function span(start: number, end: number) {
  return {
    start_seconds: start,
    end_seconds: end,
    start_beat: null,
    end_beat: null,
    start_measure: null,
    end_measure: null,
  };
}

function insight(
  id: string,
  kind: string,
  overrides: Partial<Insight> = {},
): Insight {
  return {
    id,
    version_id: "version-1",
    kind,
    claim: overrides.claim ?? kind,
    span: overrides.span ?? span(0, 1),
    entity_ids: [],
    evidence: overrides.evidence ?? {},
    confidence: null,
    provenance: {},
    created_at: new Date(0).toISOString(),
    created_by: null,
    produced_by_job_id: null,
  };
}

function chord(id: string, start: number, end: number): Insight {
  return insight(id, "chord", { span: span(start, end) });
}

describe("finding support provenance", () => {
  it("keeps single-source findings anchored to their persisted insight", () => {
    const density = insight("density-1", "rhythm_density", {
      evidence: {
        windows: [
          { start: 0, end: 2, density: 4 },
          { start: 2, end: 4, density: 12 },
        ],
      },
    });

    const peak = deriveFindings([density]).find((finding) => finding.kind === "density_peak");

    expect(peak).toBeDefined();
    expect(peak!.sourceInsightId).toBe("density-1");
    expect(peak!.supportInsightIds).toEqual(["density-1"]);
  });

  it("cites the actual later harmonic peak and the baseline window, not the first chord", () => {
    const chords = [
      chord("c1", 0, 4),
      chord("c2", 4, 8),
      chord("c3", 8, 12),
      chord("c4", 12, 13),
      chord("c5", 13, 14),
      chord("c6", 14, 15),
    ];

    const activity = deriveFindings(chords).find((finding) => finding.kind === "harmonic_activity");

    expect(activity).toBeDefined();
    expect(activity!.startSeconds).toBe(12);
    expect(activity!.sourceInsightId).toBe("c4");
    expect(activity!.sourceInsightId).not.toBe("c1");
    expect(activity!.supportInsightIds).toEqual(["c4", "c5", "c6", "c1", "c2", "c3"]);
    expect(activity!.evidence).toMatchObject({
      windowStart: 12,
      windowEnd: 15,
      baselineWindowStart: 0,
      baselineWindowEnd: 12,
    });
  });
});

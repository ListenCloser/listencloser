import { describe, expect, it } from "vitest";
import { deriveFindings, type TemporalFinding } from "@/lib/inspector/findings";
import type { Insight } from "@/lib/domain.types";

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

function makeSpan(start: number, end: number) {
  return { start_seconds: start, end_seconds: end, start_beat: null, end_beat: null, start_measure: null, end_measure: null };
}

describe("deriveFindings", () => {
  it("returns empty array when no relevant insights exist", () => {
    const findings = deriveFindings([]);
    expect(findings).toEqual([]);
  });

  it("derives density peak from rhythm_density evidence", () => {
    const densityInsight = insight({
      id: "density-1",
      kind: "rhythm_density",
      evidence: {
        windows: [
          { start: 0, end: 2, density: 5 },
          { start: 2, end: 4, density: 15 },
          { start: 4, end: 6, density: 8 },
        ],
      },
    });

    const findings = deriveFindings([densityInsight]);
    const peak = findings.find((f) => f.kind === "density_peak");

    expect(peak).toBeDefined();
    expect(peak!.startSeconds).toBe(2);
    expect(peak!.endSeconds).toBe(4);
    expect(peak!.label).toContain("Peak note density");
  });

  it("derives density valley when significantly lower than peak", () => {
    const densityInsight = insight({
      id: "density-1",
      kind: "rhythm_density",
      evidence: {
        windows: [
          { start: 0, end: 2, density: 2 },
          { start: 2, end: 4, density: 20 },
          { start: 4, end: 6, density: 8 },
        ],
      },
    });

    const findings = deriveFindings([densityInsight]);
    const valley = findings.find((f) => f.kind === "density_valley");

    expect(valley).toBeDefined();
    expect(valley!.startSeconds).toBe(0);
    expect(valley!.endSeconds).toBe(2);
    expect(valley!.label).toContain("Quieter passage");
  });

  it("does not derive valley when density is not significantly lower", () => {
    const densityInsight = insight({
      id: "density-1",
      kind: "rhythm_density",
      evidence: {
        windows: [
          { start: 0, end: 2, density: 10 },
          { start: 2, end: 4, density: 15 },
          { start: 4, end: 6, density: 12 },
        ],
      },
    });

    const findings = deriveFindings([densityInsight]);
    const valley = findings.find((f) => f.kind === "density_valley");

    expect(valley).toBeUndefined();
  });

  it("derives rest finding from rhythm_rests evidence", () => {
    const restInsight = insight({
      id: "rest-1",
      kind: "rhythm_rests",
      evidence: {
        rests: [
          { start: 0, end: 0.3, duration: 0.3 },
          { start: 4, end: 5.5, duration: 1.5 },
          { start: 8, end: 8.2, duration: 0.2 },
        ],
      },
    });

    const findings = deriveFindings([restInsight]);
    const rest = findings.find((f) => f.kind === "rest");

    expect(rest).toBeDefined();
    expect(rest!.startSeconds).toBe(4);
    expect(rest!.endSeconds).toBe(5.5);
    expect(rest!.label).toContain("Pronounced rest");
  });

  it("ignores rests shorter than 500ms", () => {
    const restInsight = insight({
      id: "rest-1",
      kind: "rhythm_rests",
      evidence: {
        rests: [
          { start: 0, end: 0.3, duration: 0.3 },
          { start: 4, end: 4.4, duration: 0.4 },
        ],
      },
    });

    const findings = deriveFindings([restInsight]);
    const rest = findings.find((f) => f.kind === "rest");

    expect(rest).toBeUndefined();
  });

  it("derives harmonic activity from chord changes", () => {
    const chords = [
      insight({ id: "c1", kind: "chord", span: makeSpan(0, 2) }),
      insight({ id: "c2", kind: "chord", span: makeSpan(2, 3) }),
      insight({ id: "c3", kind: "chord", span: makeSpan(3, 4) }),
      insight({ id: "c4", kind: "chord", span: makeSpan(4, 6) }),
      insight({ id: "c5", kind: "chord", span: makeSpan(6, 10) }),
      insight({ id: "c6", kind: "chord", span: makeSpan(10, 12) }),
    ];

    const findings = deriveFindings(chords);
    const activity = findings.find((f) => f.kind === "harmonic_activity");

    expect(activity).toBeDefined();
    expect(activity!.label).toContain("Harmonic changes become more frequent");
  });

  it("does not derive harmonic activity with fewer than 4 chords", () => {
    const chords = [
      insight({ id: "c1", kind: "chord", span: makeSpan(0, 2) }),
      insight({ id: "c2", kind: "chord", span: makeSpan(2, 4) }),
      insight({ id: "c3", kind: "chord", span: makeSpan(4, 6) }),
    ];

    const findings = deriveFindings(chords);
    const activity = findings.find((f) => f.kind === "harmonic_activity");

    expect(activity).toBeUndefined();
  });

  it("sorts findings by time", () => {
    const densityInsight = insight({
      id: "density-1",
      kind: "rhythm_density",
      evidence: {
        windows: [
          { start: 10, end: 12, density: 20 },
          { start: 0, end: 2, density: 5 },
        ],
      },
    });

    const findings = deriveFindings([densityInsight]);
    expect(findings.length).toBeGreaterThanOrEqual(1);
    for (let i = 1; i < findings.length; i++) {
      expect(findings[i].startSeconds).toBeGreaterThanOrEqual(findings[i - 1].startSeconds);
    }
  });

  it("limits findings to 8", () => {
    // Create many insights that would each produce a finding
    const insights: Insight[] = [];
    for (let i = 0; i < 20; i++) {
      insights.push(insight({
        id: `density-${i}`,
        kind: "rhythm_density",
        evidence: {
          windows: [
            { start: i * 10, end: i * 10 + 2, density: 5 },
            { start: i * 10 + 2, end: i * 10 + 4, density: 20 },
          ],
        },
      }));
    }

    const findings = deriveFindings(insights);
    expect(findings.length).toBeLessThanOrEqual(8);
  });

  it("combines findings from multiple insight types", () => {
    const densityInsight = insight({
      id: "density-1",
      kind: "rhythm_density",
      evidence: {
        windows: [
          { start: 0, end: 2, density: 5 },
          { start: 2, end: 4, density: 20 },
        ],
      },
    });

    const restInsight = insight({
      id: "rest-1",
      kind: "rhythm_rests",
      evidence: {
        rests: [{ start: 6, end: 8, duration: 2 }],
      },
    });

    const findings = deriveFindings([densityInsight, restInsight]);
    // density peak + density valley (5 < 20*0.5) + rest = 3
    expect(findings.length).toBe(3);
    expect(findings.some((f) => f.kind === "density_peak")).toBe(true);
    expect(findings.some((f) => f.kind === "density_valley")).toBe(true);
    expect(findings.some((f) => f.kind === "rest")).toBe(true);
  });
});

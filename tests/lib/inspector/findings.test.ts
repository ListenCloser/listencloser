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
  describe("sparse evidence → no bogus finding", () => {
    it("returns empty array when no relevant insights exist", () => {
      expect(deriveFindings([])).toEqual([]);
    });

    it("returns empty array for insights without rhythm_density/rhythm_rests/chord", () => {
      const insights = [
        insight({ kind: "key" }),
        insight({ kind: "tempo" }),
        insight({ kind: "time_signature" }),
      ];
      expect(deriveFindings(insights)).toEqual([]);
    });

    it("returns empty for density with only 1 window", () => {
      const densityInsight = insight({
        kind: "rhythm_density",
        evidence: { windows: [{ start: 0, end: 2, density: 10 }] },
      });
      expect(deriveFindings([densityInsight])).toEqual([]);
    });

    it("returns empty for density with all zero density", () => {
      const densityInsight = insight({
        kind: "rhythm_density",
        evidence: {
          windows: [
            { start: 0, end: 2, density: 0 },
            { start: 2, end: 4, density: 0 },
          ],
        },
      });
      expect(deriveFindings([densityInsight])).toEqual([]);
    });

    it("returns empty for rests shorter than 500ms", () => {
      const restInsight = insight({
        kind: "rhythm_rests",
        evidence: {
          rests: [
            { start: 0, end: 0.3, duration: 0.3 },
            { start: 4, end: 4.4, duration: 0.4 },
          ],
        },
      });
      expect(deriveFindings([restInsight])).toEqual([]);
    });

    it("returns empty for fewer than 4 chords", () => {
      const chords = [
        insight({ kind: "chord", span: makeSpan(0, 2) }),
        insight({ kind: "chord", span: makeSpan(2, 4) }),
        insight({ kind: "chord", span: makeSpan(4, 6) }),
      ];
      expect(deriveFindings(chords)).toEqual([]);
    });
  });

  describe("density findings", () => {
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
      expect(findings.find((f) => f.kind === "density_valley")).toBeUndefined();
    });
  });

  describe("rest findings", () => {
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
        kind: "rhythm_rests",
        evidence: {
          rests: [
            { start: 0, end: 0.3, duration: 0.3 },
            { start: 4, end: 4.4, duration: 0.4 },
          ],
        },
      });

      expect(deriveFindings([restInsight])).toEqual([]);
    });
  });

  describe("harmonic activity findings", () => {
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
        insight({ kind: "chord", span: makeSpan(0, 2) }),
        insight({ kind: "chord", span: makeSpan(2, 4) }),
        insight({ kind: "chord", span: makeSpan(4, 6) }),
      ];

      expect(deriveFindings(chords)).toEqual([]);
    });

    it("does not derive harmonic activity when density difference is small", () => {
      // All chords have similar spacing
      const chords = [
        insight({ kind: "chord", span: makeSpan(0, 2) }),
        insight({ kind: "chord", span: makeSpan(2, 4) }),
        insight({ kind: "chord", span: makeSpan(4, 6) }),
        insight({ kind: "chord", span: makeSpan(6, 8) }),
      ];

      expect(deriveFindings(chords)).toEqual([]);
    });
  });

  describe("deterministic ordering", () => {
    it("sorts findings by time", () => {
      const densityInsight = insight({
        kind: "rhythm_density",
        evidence: {
          windows: [
            { start: 10, end: 12, density: 20 },
            { start: 0, end: 2, density: 5 },
          ],
        },
      });

      const findings = deriveFindings([densityInsight]);
      for (let i = 1; i < findings.length; i++) {
        expect(findings[i].startSeconds).toBeGreaterThanOrEqual(findings[i - 1].startSeconds);
      }
    });

    it("limits findings to 8", () => {
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

      expect(deriveFindings(insights).length).toBeLessThanOrEqual(8);
    });
  });

  describe("no withheld kinds", () => {
    it("does not process cadence insights", () => {
      const cadenceInsight = insight({
        kind: "cadence",
        span: makeSpan(0, 2),
        evidence: { kind: "authentic" },
      });

      expect(deriveFindings([cadenceInsight])).toEqual([]);
    });

    it("does not process key_region insights", () => {
      const keyRegionInsight = insight({
        kind: "key_region",
        span: makeSpan(0, 4),
        evidence: { key: "C major" },
      });

      expect(deriveFindings([keyRegionInsight])).toEqual([]);
    });

    it("does not process harmonic_rhythm insights", () => {
      const harmonicRhythmInsight = insight({
        kind: "harmonic_rhythm",
        span: makeSpan(0, 4),
        evidence: { changes: 3 },
      });

      expect(deriveFindings([harmonicRhythmInsight])).toEqual([]);
    });
  });

  describe("selection filtering", () => {
    it("derives findings from selection-scoped insights", () => {
      const densityInsight = insight({
        kind: "rhythm_density",
        evidence: {
          windows: [
            { start: 0, end: 2, density: 5 },
            { start: 2, end: 4, density: 20 },
          ],
        },
      });

      // When insights are already filtered to selection, findings derive from them
      const findings = deriveFindings([densityInsight]);
      expect(findings.length).toBeGreaterThan(0);
    });
  });

  describe("combines findings from multiple insight types", () => {
    it("combines density and rest findings", () => {
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

  describe("melody findings", () => {
    it("derives melody register findings", () => {
      const registerPeak = insight({
        id: "peak-1",
        kind: "melody_register_peak",
        claim: "Highest melody note: C6",
        span: makeSpan(3.5, 4.0),
        evidence: { pitch: 84, pitch_name: "C6", type: "highest" },
      });

      const findings = deriveFindings([registerPeak]);
      expect(findings).toHaveLength(1);
      expect(findings[0].kind).toBe("melody_register_peak");
      expect(findings[0].category).toBe("melody");
      expect(findings[0].startSeconds).toBe(3.5);
    });

    it("derives melody contour findings", () => {
      const contourAscending = insight({
        id: "contour-1",
        kind: "melody_contour_ascending",
        claim: "Ascending contour: C4–G5 (19 semitones)",
        span: makeSpan(0, 4),
        evidence: { contour: "ascending", start_pitch: 60, end_pitch: 79, pitch_range: 19, note_count: 8 },
      });

      const findings = deriveFindings([contourAscending]);
      expect(findings).toHaveLength(1);
      expect(findings[0].kind).toBe("melody_contour_ascending");
      expect(findings[0].category).toBe("melody");
      expect(findings[0].label).toContain("Ascending contour");
    });

    it("derives melody activity findings", () => {
      const denseActivity = insight({
        id: "activity-1",
        kind: "melody_activity_dense",
        claim: "Dense melodic passage around 1.0s",
        span: makeSpan(0.5, 2.5),
        evidence: { note_count: 10, window_duration: 2.0, average_density: 3.5 },
      });

      const findings = deriveFindings([denseActivity]);
      expect(findings).toHaveLength(1);
      expect(findings[0].kind).toBe("melody_activity_dense");
      expect(findings[0].category).toBe("melody");
    });

    it("includes sourceInsightId for melody findings", () => {
      const registerLow = insight({
        id: "low-1",
        kind: "melody_register_low",
        claim: "Lowest melody note: C3",
        span: makeSpan(0, 0.5),
        evidence: { pitch: 48, pitch_name: "C3", type: "lowest" },
      });

      const findings = deriveFindings([registerLow]);
      expect(findings[0].sourceInsightId).toBe("low-1");
    });
  });
});

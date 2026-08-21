import { describe, expect, it } from "vitest";
import {
  extractAnnotations,
  extractDensityWindows,
  extractRestSegments,
  type AnalysisAnnotation,
} from "@/lib/analysis-annotations";
import type { Insight } from "@/lib/domain.types";

function makeInsight(
  overrides: Partial<Insight> & { kind: string; span: Insight["span"] },
): Insight {
  return {
    id: "test-id",
    version_id: "v1",
    claim: "test claim",
    entity_ids: [],
    evidence: {},
    confidence: null,
    provenance: {},
    created_at: new Date().toISOString(),
    created_by: null,
    produced_by_job_id: null,
    ...overrides,
  };
}

describe("extractAnnotations", () => {
  it("extracts rhythm_density as rhythm category", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "r1",
        kind: "rhythm_density",
        claim: "Note density profile: 10 windows",
        span: { start_seconds: 0, end_seconds: 10, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result).toHaveLength(1);
    expect(result[0].category).toBe("rhythm");
    expect(result[0].kind).toBe("rhythm_density");
    expect(result[0].startSeconds).toBe(0);
    expect(result[0].endSeconds).toBe(10);
  });

  it("extracts harmonic_rhythm as harmony category", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "h1",
        kind: "harmonic_rhythm",
        claim: "Harmonic rhythm profile: 8 windows",
        span: { start_seconds: 5, end_seconds: 20, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result).toHaveLength(1);
    expect(result[0].category).toBe("harmony");
    expect(result[0].startSeconds).toBe(5);
    expect(result[0].endSeconds).toBe(20);
  });

  it("ignores insights without time span", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "k1",
        kind: "key",
        claim: "Key: C major",
        span: { start_seconds: null, end_seconds: null, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result).toHaveLength(0);
  });

  it("ignores insights with end <= start", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "bad",
        kind: "rhythm_density",
        span: { start_seconds: 10, end_seconds: 5, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result).toHaveLength(0);
  });

  it("ignores non-temporal insight kinds", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "key1",
        kind: "key",
        claim: "Key: A minor",
        span: { start_seconds: 0, end_seconds: 30, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
      makeInsight({
        id: "chord1",
        kind: "chord",
        claim: "C:maj",
        span: { start_seconds: 0, end_seconds: 2, start_beat: 0, end_beat: 4, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result).toHaveLength(0);
  });

  it("extracts roman_numeral as theory category", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "rn1",
        kind: "roman_numeral",
        claim: "I (C major)",
        evidence: { numeral: "I", degree: 1, quality: "major" },
        span: { start_seconds: 0, end_seconds: 2, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result).toHaveLength(1);
    expect(result[0].category).toBe("theory");
    expect(result[0].kind).toBe("roman_numeral");
    expect(result[0].label).toBe("I (C major)");
  });

  it("extracts harmonic_function as theory category", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "hf1",
        kind: "harmonic_function",
        claim: "TONIC (I)",
        evidence: { function: "TONIC", numeral: "I" },
        span: { start_seconds: 0, end_seconds: 2, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result).toHaveLength(1);
    expect(result[0].category).toBe("theory");
    expect(result[0].kind).toBe("harmonic_function");
    expect(result[0].label).toBe("TONIC (I)");
  });

  it("preserves confidence from insight", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "r1",
        kind: "rhythm_density",
        confidence: 0.8,
        span: { start_seconds: 0, end_seconds: 10, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result[0].confidence).toBe(0.8);
  });

  it("handles multiple annotations correctly", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "r1",
        kind: "rhythm_density",
        span: { start_seconds: 0, end_seconds: 10, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
      makeInsight({
        id: "h1",
        kind: "harmonic_rhythm",
        span: { start_seconds: 5, end_seconds: 15, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
      makeInsight({
        id: "rest1",
        kind: "rhythm_rests",
        span: { start_seconds: 8, end_seconds: 9, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result).toHaveLength(3);
    expect(result.map((a) => a.category).sort()).toEqual(["harmony", "rhythm", "rhythm"]);
  });

  it("annotation maps to correct time span", () => {
    const insights: Insight[] = [
      makeInsight({
        id: "r1",
        kind: "rhythm_density",
        span: { start_seconds: 3.5, end_seconds: 7.2, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
      }),
    ];
    const result = extractAnnotations(insights);
    expect(result[0].startSeconds).toBe(3.5);
    expect(result[0].endSeconds).toBe(7.2);
  });
});

describe("extractDensityWindows", () => {
  it("extracts windows from evidence", () => {
    const insight = makeInsight({
      id: "r1",
      kind: "rhythm_density",
      evidence: {
        windows: [
          { start: 0, end: 2, density: 1.5 },
          { start: 2, end: 4, density: 3.0 },
        ],
      },
      span: { start_seconds: 0, end_seconds: 4, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
    });
    const result = extractDensityWindows(insight);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ start: 0, end: 2, density: 1.5 });
  });

  it("filters out invalid windows", () => {
    const insight = makeInsight({
      id: "r1",
      kind: "rhythm_density",
      evidence: {
        windows: [
          { start: 0, end: 2, density: 1.5 },
          { start: null, end: 4, density: 3.0 },
          { start: 4, end: 6 },
        ],
      },
      span: { start_seconds: 0, end_seconds: 6, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
    });
    const result = extractDensityWindows(insight);
    expect(result).toHaveLength(1);
  });

  it("returns empty when no windows in evidence", () => {
    const insight = makeInsight({
      id: "r1",
      kind: "rhythm_density",
      evidence: {},
      span: { start_seconds: 0, end_seconds: 4, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
    });
    expect(extractDensityWindows(insight)).toHaveLength(0);
  });
});

describe("extractRestSegments", () => {
  it("extracts rest segments from evidence", () => {
    const insight = makeInsight({
      id: "rest1",
      kind: "rhythm_rests",
      evidence: {
        rests: [
          { start: 2.0, end: 5.0, duration: 3.0 },
          { start: 8.0, end: 10.0, duration: 2.0 },
        ],
      },
      span: { start_seconds: 0, end_seconds: 12, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
    });
    const result = extractRestSegments(insight);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ start: 2.0, end: 5.0, duration: 3.0 });
  });

  it("returns empty when no rests in evidence", () => {
    const insight = makeInsight({
      id: "rest1",
      kind: "rhythm_rests",
      evidence: {},
      span: { start_seconds: 0, end_seconds: 12, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
    });
    expect(extractRestSegments(insight)).toHaveLength(0);
  });
});

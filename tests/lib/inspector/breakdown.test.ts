import { describe, expect, it } from "vitest";
import { rankBreakdownFindings } from "@/lib/inspector/breakdown";
import type { TemporalFinding } from "@/lib/inspector/findings";

function finding(overrides: Partial<TemporalFinding>): TemporalFinding {
  return {
    id: overrides.id ?? "finding-1",
    sourceInsightId: overrides.sourceInsightId ?? "insight-1",
    kind: overrides.kind ?? "density_peak",
    category: overrides.category ?? "rhythm",
    startSeconds: overrides.startSeconds ?? 10,
    endSeconds: overrides.endSeconds ?? 12,
    label: overrides.label ?? "Highest observed note-onset density around 0:10",
    evidence: overrides.evidence ?? { density: 12 },
  };
}

describe("rankBreakdownFindings", () => {
  it("returns no invented findings for sparse evidence", () => {
    expect(rankBreakdownFindings([])).toEqual([]);
  });

  it("strongly prioritizes findings that overlap the active selection", () => {
    const wholeWorkPeak = finding({
      id: "peak",
      sourceInsightId: "density-1",
      kind: "density_peak",
      startSeconds: 2,
      endSeconds: 4,
    });
    const selectedRest = finding({
      id: "rest",
      sourceInsightId: "rests-1",
      kind: "rest",
      startSeconds: 42,
      endSeconds: 44,
      evidence: { duration: 2 },
    });

    const ranked = rankBreakdownFindings([wholeWorkPeak, selectedRest], { start: 40, end: 50 });

    expect(ranked[0].kind).toBe("rest");
    expect(ranked[0].startSeconds).toBe(42);
  });

  it("uses salience rather than chronology for the whole-work Breakdown", () => {
    const earlyRest = finding({
      id: "rest",
      sourceInsightId: "rests-1",
      kind: "rest",
      startSeconds: 1,
      endSeconds: 2,
      evidence: { duration: 1 },
    });
    const laterHarmony = finding({
      id: "harmony",
      sourceInsightId: "chord-1",
      kind: "harmonic_activity",
      category: "harmony",
      startSeconds: 30,
      endSeconds: 36,
      evidence: { chordDensity: 1.4 },
    });

    const ranked = rankBreakdownFindings([earlyRest, laterHarmony]);

    expect(ranked[0].kind).toBe("harmonic_activity");
  });

  it("collapses peak and valley views derived from the same density measurement", () => {
    const peak = finding({
      id: "peak",
      sourceInsightId: "density-1",
      kind: "density_peak",
      startSeconds: 8,
      endSeconds: 10,
    });
    const valley = finding({
      id: "valley",
      sourceInsightId: "density-1",
      kind: "density_valley",
      startSeconds: 18,
      endSeconds: 20,
    });

    const ranked = rankBreakdownFindings([valley, peak]);

    expect(ranked).toHaveLength(1);
    expect(ranked[0].kind).toBe("density_peak");
  });

  it("keeps experimental melody findings explicitly experimental", () => {
    const melody = finding({
      id: "melody-peak",
      sourceInsightId: "melody-1",
      kind: "melody_register_peak",
      category: "melody",
      startSeconds: 12,
      endSeconds: 13,
      label: "Melody: Highest register here",
      evidence: { pitch: 79 },
    });

    const [ranked] = rankBreakdownFindings([melody]);

    expect(ranked.maturity).toBe("experimental");
    expect(ranked.trustClass).toBe("deterministic_derived");
    expect(ranked.evidenceSummary).toContain("experimental melody extraction");
    expect(ranked.primaryRepresentation).toBe("piano_roll");
  });

  it("does not let experimental melody displace same-scope production findings", () => {
    const experimentalMelody = finding({
      id: "melody-peak",
      sourceInsightId: "melody-1",
      kind: "melody_register_peak",
      category: "melody",
      startSeconds: 12,
      endSeconds: 13,
      evidence: { pitch: 79, register: "high", contour: "peak", activity: 2 },
    });
    const productionValley = finding({
      id: "density-valley",
      sourceInsightId: "density-2",
      kind: "density_valley",
      category: "rhythm",
      startSeconds: 16,
      endSeconds: 18,
      evidence: {},
    });

    const ranked = rankBreakdownFindings([experimentalMelody, productionValley]);

    expect(ranked.map((item) => item.kind)).toEqual(["density_valley", "melody_register_peak"]);
  });

  it("uses current truthful language for harmonic activity", () => {
    const harmony = finding({
      kind: "harmonic_activity",
      category: "harmony",
      sourceInsightId: "chords",
      startSeconds: 15,
      endSeconds: 20,
      evidence: { chordDensity: 1.8 },
    });

    const [ranked] = rankBreakdownFindings([harmony]);

    expect(ranked.headline).toBe("Chord changes become more frequent in this passage.");
    expect(ranked.evidenceSummary).toContain("change rate, not harmonic tension");
  });

  it("caps the compact Breakdown at the requested number of promoted findings", () => {
    const candidates = Array.from({ length: 8 }, (_, index) => finding({
      id: `rest-${index}`,
      sourceInsightId: `rest-insight-${index}`,
      kind: "rest",
      startSeconds: index * 3,
      endSeconds: index * 3 + 1,
      evidence: { duration: 1 },
    }));

    expect(rankBreakdownFindings(candidates, null, 3)).toHaveLength(3);
    expect(rankBreakdownFindings(candidates, null, 0)).toEqual([]);
  });

  it("rejects invalid temporal candidates rather than making them actionable", () => {
    const invalid = finding({ startSeconds: 10, endSeconds: 10 });
    expect(rankBreakdownFindings([invalid])).toEqual([]);
  });
});

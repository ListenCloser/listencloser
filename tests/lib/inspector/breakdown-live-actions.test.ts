import { describe, expect, it } from "vitest";
import {
  resolveBreakdownFindingActions,
  type BreakdownActionContext,
} from "@/lib/inspector/breakdown-actions";
import { rankBreakdownFindings } from "@/lib/inspector/breakdown";
import type { TemporalFinding } from "@/lib/inspector/findings";

function rankedFinding(overrides: Partial<TemporalFinding> = {}) {
  const source: TemporalFinding = {
    id: "density-peak",
    sourceInsightId: "density-source",
    supportInsightIds: ["density-source"],
    kind: "density_peak",
    category: "rhythm",
    startSeconds: 12,
    endSeconds: 15,
    label: "Peak note density around 0:12",
    evidence: { density: 9 },
    ...overrides,
  };
  return rankBreakdownFindings([source])[0];
}

function context(overrides: Partial<BreakdownActionContext> = {}): BreakdownActionContext {
  return {
    activeSourceRole: "original",
    durationSeconds: 60,
    availableRepresentationKinds: ["waveform", "piano_roll"],
    activeRepresentation: "piano_roll",
    activeWorkId: "work-1",
    sourceInsightKind: "rhythm_density",
    ...overrides,
  };
}

describe("live Breakdown action resolution", () => {
  it("loops only when a performance-time source and bounded duration can execute the span", () => {
    const finding = rankedFinding();

    expect(resolveBreakdownFindingActions(finding, context()).map((action) => action.type)).toContain("loop");
    expect(resolveBreakdownFindingActions(finding, context({ activeSourceRole: "score" })).map((action) => action.type)).not.toContain("loop");
    expect(resolveBreakdownFindingActions(finding, context({ activeSourceRole: null })).map((action) => action.type)).not.toContain("loop");
    expect(resolveBreakdownFindingActions(finding, context({ durationSeconds: 14 })).map((action) => action.type)).not.toContain("loop");
  });

  it("shows only the finding's preferred representation when that view really exists", () => {
    const finding = rankedFinding();

    expect(resolveBreakdownFindingActions(
      finding,
      context({ activeRepresentation: "piano_roll" }),
    )).toContainEqual({ type: "show", representationId: "listen" });
    expect(resolveBreakdownFindingActions(
      finding,
      context({ activeRepresentation: "listen" }),
    ).map((action) => action.type)).not.toContain("show");
    expect(resolveBreakdownFindingActions(
      finding,
      context({ availableRepresentationKinds: ["piano_roll"] }),
    ).map((action) => action.type)).not.toContain("show");
  });

  it("withholds Ask for Inspector-visible evidence the backend marks ask:false", () => {
    const finding = rankedFinding();

    expect(resolveBreakdownFindingActions(finding, context()).map((action) => action.type)).not.toContain("ask");
    expect(resolveBreakdownFindingActions(
      finding,
      context({ sourceInsightKind: "rhythm_rests" }),
    ).map((action) => action.type)).not.toContain("ask");
  });

  it("offers Ask for an Ask-exposed source capability when a work is open", () => {
    const harmonic = rankedFinding({
      id: "harmonic",
      sourceInsightId: "chord-source",
      supportInsightIds: ["chord-source"],
      kind: "harmonic_activity",
      category: "harmony",
      label: "Harmonic changes become more frequent",
    });

    expect(resolveBreakdownFindingActions(
      harmonic,
      context({ sourceInsightKind: "chord" }),
    ).map((action) => action.type)).toContain("ask");
    expect(resolveBreakdownFindingActions(
      harmonic,
      context({ sourceInsightKind: "chord", activeWorkId: null }),
    ).map((action) => action.type)).not.toContain("ask");
  });

  it("never invents Compare from a single finding", () => {
    const actions = resolveBreakdownFindingActions(
      rankedFinding(),
      context({ sourceInsightKind: "chord" }),
    );

    expect(actions.map((action) => action.type)).toEqual(["loop", "show", "ask"]);
    expect(actions.some((action) => (action as { type: string }).type === "compare")).toBe(false);
  });
});

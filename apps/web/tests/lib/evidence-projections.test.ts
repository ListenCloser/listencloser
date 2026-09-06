import { describe, expect, it } from "vitest";
import type { Insight } from "@/lib/domain.types";
import {
  presentationFamilyForKind,
  projectionPolicyForKind,
  resolveEvidenceProjection,
  resolveInsightProjection,
} from "@/lib/evidence-projections";

describe("evidence projection policy", () => {
  it("treats a sufficiently aligned chord as a native score symbol", () => {
    const exact = resolveEvidenceProjection("chord", "score", "exact");
    const adequate = resolveEvidenceProjection("chord", "score", "adequate");

    expect(exact).toMatchObject({ mode: "score-symbol", native: true, precision: "exact" });
    expect(adequate).toMatchObject({ mode: "score-symbol", native: true, precision: "adequate" });
  });

  it("falls an approximately aligned score chord back to a non-passive locator region", () => {
    expect(resolveEvidenceProjection("chord", "score", "approximate")).toEqual({
      kind: "chord",
      target: "score",
      mode: "score-region",
      precision: "approximate",
      native: false,
      passiveByDefault: false,
      requiresContext: [],
    });
  });

  it("uses a harmony lane on piano roll but only a locator on spectrogram", () => {
    expect(resolveEvidenceProjection("chord", "piano_roll", "adequate")).toMatchObject({
      mode: "ruler-segment",
      native: true,
      passiveByDefault: true,
    });
    expect(resolveEvidenceProjection("chord", "spectrogram", "adequate")).toMatchObject({
      mode: "time-region",
      native: false,
      passiveByDefault: false,
    });
  });

  it("keeps Roman numeral and function secondary and key-dependent", () => {
    const numeral = projectionPolicyForKind("roman_numeral", "score");
    const harmonicFunction = projectionPolicyForKind("harmonic_function", "score");

    expect(numeral.passiveByDefault).toBe(false);
    expect(numeral.requiresContext).toEqual(["key"]);
    expect(harmonicFunction.passiveByDefault).toBe(false);
    expect(harmonicFunction.requiresContext).toEqual(["key"]);

    expect(resolveEvidenceProjection("roman_numeral", "score", "adequate")).toEqual({
      kind: "roman_numeral",
      target: "score",
      mode: "score-symbol",
      precision: "adequate",
      native: true,
      passiveByDefault: false,
      requiresContext: ["key"],
    });
  });

  it("allows coarse score location for localized activity without pretending it is notation-native", () => {
    expect(resolveEvidenceProjection("rhythm_density", "score", "approximate")).toMatchObject({
      mode: "score-region",
      native: false,
      precision: "approximate",
    });
    expect(resolveEvidenceProjection("rhythm_rests", "score", "approximate")).toMatchObject({
      mode: "score-region",
      native: false,
      precision: "approximate",
    });
  });

  it("fails closed with the complete unsupported contract for unknown evidence", () => {
    expect(resolveEvidenceProjection("unknown_detector_output", "listen", "exact")).toEqual({
      kind: "unknown_detector_output",
      target: "listen",
      mode: "none",
      precision: "unsupported",
      native: false,
      passiveByDefault: false,
      requiresContext: [],
    });
  });

  it("fails closed with the complete unsupported contract when precision is unsupported", () => {
    expect(resolveEvidenceProjection("chord", "score", "unsupported")).toEqual({
      kind: "chord",
      target: "score",
      mode: "none",
      precision: "unsupported",
      native: false,
      passiveByDefault: false,
      requiresContext: [],
    });
    expect(resolveEvidenceProjection("cadence", "score", "exact").mode).toBe("none");
  });

  it("keeps the Insight convenience path behaviorally identical to kind-based resolution", () => {
    const insight = { kind: "chord" } as Insight;
    expect(resolveInsightProjection(insight, "score", "adequate")).toEqual(
      resolveEvidenceProjection("chord", "score", "adequate"),
    );
  });

  it("preserves the current presentation families without making them the projection ontology", () => {
    expect(presentationFamilyForKind("rhythm_density")).toBe("rhythm");
    expect(presentationFamilyForKind("harmonic_rhythm")).toBe("harmony");
    expect(presentationFamilyForKind("chord")).toBe("theory");
    expect(presentationFamilyForKind("key")).toBeNull();
  });
});

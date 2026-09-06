import { describe, expect, it } from "vitest";

import {
  ANALYSIS_DISCOVERY_DEFINITIONS,
  DISCOVERABILITY_TASK_CASES,
  FUTURE_DISCOVERY_DECISIONS,
  PRODUCT_INSPECTION_RUNTIME_EXCEPTIONS,
  validateProductInspectionReachability,
} from "@/components/workspace/analysis-product-contract";

describe("analysis product contract", () => {
  it("keeps discovery labels in musician-facing vocabulary", () => {
    const definitions = Object.values(ANALYSIS_DISCOVERY_DEFINITIONS);
    const engineVocabulary = [
      "chordmini",
      "clamp",
      "librosa",
      "midibert",
      "pesto",
      "pyin",
      "torchcrepe",
    ];

    expect(definitions.length).toBeGreaterThanOrEqual(5);
    for (const definition of definitions) {
      expect(definition.searchAliases.length).toBeGreaterThan(0);
      const primaryCopy = `${definition.title} ${definition.description}`.toLowerCase();
      for (const engineName of engineVocabulary) {
        expect(primaryCopy).not.toContain(engineName);
      }
    }
  });

  it("keeps current task-language fixtures mapped to real discovery rows", () => {
    for (const taskCase of DISCOVERABILITY_TASK_CASES) {
      expect(taskCase.task.trim().length).toBeGreaterThan(0);
      expect(ANALYSIS_DISCOVERY_DEFINITIONS[taskCase.expected]).toBeDefined();
    }
  });

  it("tracks ChordMini as a real-product runtime whose UI tail is still owned", () => {
    const chordMini = PRODUCT_INSPECTION_RUNTIME_EXCEPTIONS.find(
      (entry) => entry.runtimeId === "chordmini",
    );

    expect(chordMini).toMatchObject({
      capability: "chord",
      reachability: "MISSING_UI",
      followUpIssue: 1194,
    });
    expect(() => validateProductInspectionReachability(PRODUCT_INSPECTION_RUNTIME_EXCEPTIONS)).not.toThrow();
  });

  it("rejects a MISSING_UI product runtime with no focused follow-up", () => {
    expect(() => validateProductInspectionReachability([{
      runtimeId: "example-runtime",
      capability: "example",
      reachability: "MISSING_UI",
    }])).toThrow(/focused UI follow-up/);
  });

  it("records a placement decision for Find before #1254 becomes user-reachable", () => {
    expect(FUTURE_DISCOVERY_DECISIONS.findWithinWork.issue).toBe(1254);
    expect(FUTURE_DISCOVERY_DECISIONS.findWithinWork.decision).toContain("Add analysis");
    expect(FUTURE_DISCOVERY_DECISIONS.findWithinWork.decision).toContain("before adding any global search UI");
  });
});

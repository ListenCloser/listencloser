import { describe, expect, it } from "vitest";

import {
  ANALYSIS_DISCOVERY_DEFINITIONS,
  DISCOVERABILITY_TASK_CASES,
  FUTURE_DISCOVERY_DECISIONS,
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

  it("keeps current task-language fixtures mapped to discoverable user terms", () => {
    for (const taskCase of DISCOVERABILITY_TASK_CASES) {
      const definition = ANALYSIS_DISCOVERY_DEFINITIONS[taskCase.expected];
      const task = taskCase.task.toLowerCase();

      expect(task.trim().length).toBeGreaterThan(0);
      expect(definition).toBeDefined();
      expect(definition.searchAliases.some((alias) => task.includes(alias))).toBe(true);
    }
  });

  it("records a placement decision for Find before #1254 becomes user-reachable", () => {
    expect(FUTURE_DISCOVERY_DECISIONS.findWithinWork.issue).toBe(1254);
    expect(FUTURE_DISCOVERY_DECISIONS.findWithinWork.decision).toContain("Add analysis");
    expect(FUTURE_DISCOVERY_DECISIONS.findWithinWork.decision).toContain("before adding any global search UI");
  });
});

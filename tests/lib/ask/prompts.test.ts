import { describe, expect, it } from "vitest";
import { deriveAskContext } from "@/lib/ask/context";
import { deriveAskStarterPrompts } from "@/lib/ask/prompts";
import type { AskContext } from "@/lib/ask/types";
import type { Insight } from "@/lib/domain.types";

function insight(id: string, kind: string, start: number | null = null, end: number | null = null): Insight {
  return {
    id,
    version_id: "version-1",
    kind,
    claim: `${kind} evidence`,
    span: {
      start_seconds: start,
      end_seconds: end,
      start_beat: null,
      end_beat: null,
      start_measure: null,
      end_measure: null,
    },
    entity_ids: [],
    evidence: {},
    confidence: null,
    provenance: {},
    created_at: new Date(0).toISOString(),
    created_by: null,
    produced_by_job_id: null,
  };
}

function context(
  entries: Array<{ insight: Insight; category: "selection" | "whole-work" }>,
  selected = false,
): AskContext {
  return {
    workId: "work-1",
    representationId: "listen",
    currentTime: 0,
    playbackSourceId: null,
    selection: selected
      ? {
          timeRange: { start: 10, end: 20, domain: "performance" },
          provenance: { origin: null, timeExact: false, measureApproximate: true },
        }
      : null,
    visibleInsights: entries,
  };
}

describe("deriveAskStarterPrompts", () => {
  it("offers no generic starter when there is no grounded context", () => {
    expect(deriveAskStarterPrompts(null)).toEqual([]);
    expect(deriveAskStarterPrompts(context([]))).toEqual([]);
  });

  it("uses selection-scoped harmony plus whole-work key for a relational question", () => {
    const prompts = deriveAskStarterPrompts(context([
      { insight: insight("chord-1", "chord", 12, 14), category: "selection" },
      { insight: insight("key-1", "key"), category: "whole-work" },
    ], true));

    expect(prompts).toEqual([
      "How do the detected chord changes in this selection relate to the detected key?",
    ]);
  });

  it("does not imply selection evidence when only whole-work evidence is available", () => {
    const prompts = deriveAskStarterPrompts(context([
      { insight: insight("key-1", "key"), category: "whole-work" },
      { insight: insight("tempo-1", "tempo"), category: "whole-work" },
    ], true));

    expect(prompts).toEqual([]);
  });

  it("does not generate a rhythm starter from ask:false density evidence", () => {
    const selection = {
      timeRange: { start: 10, end: 20, domain: "performance" as const },
      provenance: { origin: null, timeExact: false, measureApproximate: true },
    };
    const askContext = deriveAskContext(
      "work-1",
      "listen",
      10,
      null,
      selection,
      [insight("density-1", "rhythm_density", 12, 14)],
      120,
    );

    expect(askContext?.visibleInsights).toEqual([]);
    expect(deriveAskStarterPrompts(askContext)).toEqual([]);
  });

  it("does not claim meter when only tempo evidence exists", () => {
    expect(deriveAskStarterPrompts(context([
      { insight: insight("tempo-1", "tempo"), category: "whole-work" },
    ]))).toEqual(["What tempo is detected in this recording?"]);
  });

  it("does not claim tempo when only meter evidence exists", () => {
    expect(deriveAskStarterPrompts(context([
      { insight: insight("meter-1", "time_signature"), category: "whole-work" },
    ]))).toEqual(["What meter is detected in this recording?"]);
  });

  it("offers only supported whole-work questions and caps them at three", () => {
    const prompts = deriveAskStarterPrompts(context([
      { insight: insight("key-1", "key"), category: "whole-work" },
      { insight: insight("chord-1", "chord"), category: "whole-work" },
      { insight: insight("tempo-1", "tempo"), category: "whole-work" },
      { insight: insight("meter-1", "time_signature"), category: "whole-work" },
      { insight: insight("melody-1", "melody"), category: "whole-work" },
    ]));

    expect(prompts).toEqual([
      "How do the detected chords relate to the detected key?",
      "What do the detected tempo and meter show in this recording?",
      "What does the detected melody evidence show across the recording?",
    ]);
    expect(prompts).not.toContain("What stands out in this recording?");
  });
});

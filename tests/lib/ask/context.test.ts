import { describe, expect, it } from "vitest";
import { deriveAskContext } from "@/lib/ask/context";
import type { Insight } from "@/lib/domain.types";
import type { PlaybackSource } from "@/lib/stores/transport";
import type { MusicalSelection } from "@/lib/stores/workspace";

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

function timeSpan(start: number, end: number): NonNullable<Insight["span"]> {
  return { start_seconds: start, end_seconds: end, start_beat: null, end_beat: null, start_measure: null, end_measure: null };
}

const perfSource: PlaybackSource = {
  id: "perf",
  label: "Original",
  url: "data:audio/wav;base64,perf",
  kind: "audio",
  role: "original",
};

const selection: MusicalSelection = {
  timeRange: { start: 10, end: 20, domain: "performance" },
  provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
};

describe("deriveAskContext", () => {
  it("returns null when no work is loaded", () => {
    expect(deriveAskContext(null, null, 0, null, null, [], 120)).toBeNull();
  });

  it("includes the selection when present", () => {
    const ctx = deriveAskContext("work-1", "listen", 15, perfSource, selection, [], 120);
    expect(ctx?.selection).toBe(selection);
  });

  it("includes the current representation", () => {
    const ctx = deriveAskContext("work-1", "score", 15, perfSource, null, [], 120);
    expect(ctx?.representationId).toBe("score");
  });

  it("defaults the representation to listen when none is set", () => {
    const ctx = deriveAskContext("work-1", null, 15, perfSource, null, [], 120);
    expect(ctx?.representationId).toBe("listen");
  });

  it("includes the active playback source id", () => {
    const ctx = deriveAskContext("work-1", "listen", 15, perfSource, null, [], 120);
    expect(ctx?.playbackSourceId).toBe("perf");
  });

  it("exposes playback source as null when none is active", () => {
    const ctx = deriveAskContext("work-1", "listen", 15, null, null, [], 120);
    expect(ctx?.playbackSourceId).toBeNull();
  });

  it("includes current time", () => {
    const ctx = deriveAskContext("work-1", "listen", 12.5, perfSource, null, [], 120);
    expect(ctx?.currentTime).toBe(12.5);
  });

  it("keeps whole-work insights distinguishable from selection-scoped insights", () => {
    const selectionInsight = insight({ id: "sel-1", kind: "chord", span: timeSpan(12, 16) });
    const wholeWorkInsight = insight({ id: "whole-1", kind: "key" });
    const unrelatedInsight = insight({ id: "unrel-1", kind: "chord", span: timeSpan(100, 120) });

    const ctx = deriveAskContext(
      "work-1", "listen", 15, perfSource, selection,
      [selectionInsight, wholeWorkInsight, unrelatedInsight], 120,
    );

    expect(ctx?.visibleInsights).toHaveLength(2);
    const byId = Object.fromEntries((ctx?.visibleInsights ?? []).map((c) => [c.insight.id, c.category]));
    expect(byId["sel-1"]).toBe("selection");
    expect(byId["whole-1"]).toBe("whole-work");
    expect(byId["unrel-1"]).toBeUndefined();
  });

  it("does not duplicate authoritative state (same object references)", () => {
    const selectionInsight = insight({ id: "sel-1", kind: "chord", span: timeSpan(12, 16) });
    const ctx = deriveAskContext("work-1", "listen", 15, perfSource, selection, [selectionInsight], 120);
    expect(ctx?.selection).toBe(selection);
    expect(ctx?.visibleInsights[0].insight).toBe(selectionInsight);
    expect(ctx?.playbackSourceId).toBe(perfSource.id);
  });
});

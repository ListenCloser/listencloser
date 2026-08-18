import { describe, expect, it } from "vitest";
import {
  actionLabel,
  canSeekInDomain,
  describeAskContext,
  formatReference,
  formatTimeRange,
  playbackSourceDomain,
  resolveReference,
  validateAction,
} from "@/lib/ask/render";
import type { AskReference, AskAction } from "@/lib/ask/types";
import type { Insight } from "@/lib/domain.types";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { PlaybackSource } from "@/lib/stores/transport";

function perfSource(role: PlaybackSource["role"] = "original"): PlaybackSource {
  return { id: "src", label: "Source", url: "data:audio/wav;base64,x", kind: "audio", role };
}

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

describe("playbackSourceDomain", () => {
  it("treats the score rendition as the notation timeline and everything else as performance", () => {
    expect(playbackSourceDomain(perfSource("original"))).toBe("performance");
    expect(playbackSourceDomain(perfSource("transcription"))).toBe("performance");
    expect(playbackSourceDomain(perfSource("derived"))).toBe("performance");
    expect(playbackSourceDomain(perfSource("score"))).toBe("notation");
    expect(playbackSourceDomain(null)).toBeNull();
  });
});

describe("canSeekInDomain", () => {
  it("allows seeking when the reference domain matches the active source", () => {
    expect(canSeekInDomain("performance", perfSource("original"))).toBe(true);
    expect(canSeekInDomain("notation", perfSource("score"))).toBe(true);
  });

  it("rejects cross-domain seeking (never silently maps performance ↔ notation)", () => {
    expect(canSeekInDomain("notation", perfSource("original"))).toBe(false);
    expect(canSeekInDomain("performance", perfSource("score"))).toBe(false);
    expect(canSeekInDomain("performance", null)).toBe(false);
  });
});

describe("describeAskContext", () => {
  it("says Whole piece with no selection", () => {
    expect(describeAskContext(null)).toBe("Whole piece");
  });

  it("shows a time range when the selection has one", () => {
    const selection: MusicalSelection = {
      timeRange: { start: 31, end: 38, domain: "performance" },
      provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
    };
    expect(describeAskContext(selection)).toBe("0:31–0:38");
  });

  it("shows measures when the selection has a measure range", () => {
    const selection: MusicalSelection = {
      measureRange: { start: 15, end: 18 },
      provenance: { origin: "score", timeExact: false, measureApproximate: false },
    };
    expect(describeAskContext(selection)).toBe("Measures 15–18");
  });
});

describe("formatReference", () => {
  const resolveInsight = (id: string) => (id === "known" ? "Key: A minor" : null);

  it("renders time references as a time range", () => {
    expect(formatReference({ type: "time", start: 31, end: 38, domain: "performance" }, resolveInsight)).toBe("0:31–0:38");
  });

  it("renders measure references", () => {
    expect(formatReference({ type: "measure", start: 15, end: 18 }, resolveInsight)).toBe("Measures 15–18");
    expect(formatReference({ type: "measure", start: 3 }, resolveInsight)).toBe("Measure 3");
  });

  it("renders notes references with a count", () => {
    expect(formatReference({ type: "notes", ids: ["a", "b", "c"] }, resolveInsight)).toBe("Notes (3)");
  });

  it("renders resolvable insight references with their claim and falls back neutrally otherwise", () => {
    expect(formatReference({ type: "insight", id: "known" }, resolveInsight)).toBe("Key: A minor");
    expect(formatReference({ type: "insight", id: "unknown" }, resolveInsight)).toBe("Insight");
  });
});

describe("formatTimeRange", () => {
  it("formats a single time point and a range", () => {
    expect(formatTimeRange(31, 38)).toBe("0:31–0:38");
    expect(formatTimeRange(65)).toBe("1:05–1:05");
  });
});

describe("resolveReference — time", () => {
  it("seeks a performance-domain reference when the active source is performance", () => {
    const resolution = resolveReference(
      { type: "time", start: 4, end: 8, domain: "performance" },
      { activeSource: perfSource("original"), insights: [], bpm: 120, measureStarts: [], scoreDuration: null, notes: [] },
    );
    expect(resolution).toEqual({ kind: "seek", seconds: 4 });
  });

  it("blocks a notation-domain reference when the active source is performance", () => {
    const resolution = resolveReference(
      { type: "time", start: 4, end: 8, domain: "notation" },
      { activeSource: perfSource("original"), insights: [], bpm: 120, measureStarts: [], scoreDuration: null, notes: [] },
    );
    expect(resolution.kind).toBe("blocked");
  });

  it("blocks any time reference when no source is active", () => {
    const resolution = resolveReference(
      { type: "time", start: 4, domain: "performance" },
      { activeSource: null, insights: [], bpm: 120, measureStarts: [], scoreDuration: null, notes: [] },
    );
    expect(resolution.kind).toBe("blocked");
  });
});

describe("resolveReference — measure", () => {
  it("opens the Score when no trustworthy measure→time mapping exists", () => {
    const resolution = resolveReference(
      { type: "measure", start: 2, end: 4 },
      { activeSource: perfSource("original"), insights: [], bpm: 120, measureStarts: [], scoreDuration: null, notes: [] },
    );
    expect(resolution).toEqual({ kind: "open-representation", representationId: "score" });
  });

  it("seeks to the measure start when measure data is present and the score source is active", () => {
    const resolution = resolveReference(
      { type: "measure", start: 2, end: 4 },
      { activeSource: perfSource("score"), insights: [], bpm: 120, measureStarts: [0, 2, 4, 6, 8], scoreDuration: 10, notes: [] },
    );
    expect(resolution).toEqual({ kind: "seek", seconds: 4 });
  });
});

describe("resolveReference — notes", () => {
  it("selects the referenced notes on Piano Roll when they resolve cleanly", () => {
    const notes = [{ id: "n1", start: 0, end: 1 }, { id: "n2", start: 1, end: 2 }];
    const resolution = resolveReference(
      { type: "notes", ids: ["n1", "n2"] },
      { activeSource: perfSource("original"), insights: [], bpm: 120, measureStarts: [], scoreDuration: null, notes },
    );
    expect(resolution).toEqual({ kind: "select-notes", representationId: "piano_roll", ids: ["n1", "n2"] });
  });

  it("falls back to opening Piano Roll when the ids cannot be resolved", () => {
    const resolution = resolveReference(
      { type: "notes", ids: ["ghost"] },
      { activeSource: perfSource("original"), insights: [], bpm: 120, measureStarts: [], scoreDuration: null, notes: [{ id: "n1", start: 0, end: 1 }] },
    );
    expect(resolution).toEqual({ kind: "open-representation", representationId: "piano_roll" });
  });
});

describe("resolveReference — insight", () => {
  it("seeks to the insight start when it has a defensible location", () => {
    const target = insight({ id: "ins-1", kind: "section", span: { start_seconds: 12, end_seconds: 16, start_beat: null, end_beat: null, start_measure: null, end_measure: null } });
    const resolution = resolveReference(
      { type: "insight", id: "ins-1" },
      { activeSource: perfSource("original"), insights: [target], bpm: 120, measureStarts: [], scoreDuration: null, notes: [] },
    );
    expect(resolution).toEqual({ kind: "seek", seconds: 12 });
  });

  it("derives seconds from a beat when only a beat is available", () => {
    const target = insight({ id: "ins-1", kind: "section", span: { start_seconds: null, end_seconds: null, start_beat: 8, end_beat: null, start_measure: null, end_measure: null } });
    const resolution = resolveReference(
      { type: "insight", id: "ins-1" },
      { activeSource: perfSource("original"), insights: [target], bpm: 120, measureStarts: [], scoreDuration: null, notes: [] },
    );
    expect(resolution).toEqual({ kind: "seek", seconds: 4 });
  });

  it("never seeks to 0 for an insight with no defensible location", () => {
    const target = insight({ id: "ins-1", kind: "key" });
    const resolution = resolveReference(
      { type: "insight", id: "ins-1" },
      { activeSource: perfSource("original"), insights: [target], bpm: 120, measureStarts: [], scoreDuration: null, notes: [] },
    );
    expect(resolution).toEqual({ kind: "blocked", reason: "This insight has no reliable location to jump to." });
  });

  it("blocks an insight that is no longer present", () => {
    const resolution = resolveReference(
      { type: "insight", id: "gone" },
      { activeSource: perfSource("original"), insights: [], bpm: 120, measureStarts: [], scoreDuration: null, notes: [] },
    );
    expect(resolution.kind).toBe("blocked");
  });
});

describe("actionLabel", () => {
  it("labels seek and loop actions generically", () => {
    const seek: AskAction = { type: "seek", seconds: 4, domain: "performance" };
    const loop: AskAction = { type: "loop", start: 4, end: 8, domain: "performance" };
    expect(actionLabel(seek)).toBe("Jump to time");
    expect(actionLabel(loop)).toBe("Loop passage");
  });

  it("derives show_representation labels from the canonical registry for different targets", () => {
    const score: AskAction = { type: "show_representation", representationId: "score" };
    const pianoRoll: AskAction = { type: "show_representation", representationId: "piano_roll" };
    const listen: AskAction = { type: "show_representation", representationId: "listen" };
    expect(actionLabel(score)).toBe("Open Score");
    expect(actionLabel(pianoRoll)).toBe("Open Piano Roll");
    expect(actionLabel(listen)).toBe("Open Waveform");
  });

  it("falls back neutrally for an unknown representation id", () => {
    const action = { type: "show_representation", representationId: "harmony" } as unknown as AskAction;
    expect(actionLabel(action)).toBe("Action");
  });
});

describe("validateAction", () => {
  it("allows a performance seek against a performance source", () => {
    const action: AskAction = { type: "seek", seconds: 4, domain: "performance" };
    expect(validateAction(action, perfSource("original"))).toEqual({ allowed: true });
  });

  it("blocks a notation seek when the active source is performance", () => {
    const action: AskAction = { type: "seek", seconds: 4, domain: "notation" };
    expect(validateAction(action, perfSource("original")).allowed).toBe(false);
  });

  it("blocks a performance loop when the active source is the score", () => {
    const action: AskAction = { type: "loop", start: 4, end: 8, domain: "performance" };
    expect(validateAction(action, perfSource("score")).allowed).toBe(false);
  });

  it("allows a notation loop against the score source", () => {
    const action: AskAction = { type: "loop", start: 4, end: 8, domain: "notation" };
    expect(validateAction(action, perfSource("score"))).toEqual({ allowed: true });
  });

  it("rejects a show_representation action for an unknown representation id", () => {
    const action = { type: "show_representation", representationId: "harmony" } as unknown as AskAction;
    expect(validateAction(action, perfSource("original")).allowed).toBe(false);
  });

  it("accepts a show_representation action for a canonical representation", () => {
    const action: AskAction = { type: "show_representation", representationId: "score" };
    expect(validateAction(action, perfSource("original"))).toEqual({ allowed: true });
  });
});
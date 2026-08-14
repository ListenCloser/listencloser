import { describe, expect, it } from "vitest";
import { deriveInspectorContext } from "@/lib/inspector/context";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { PlaybackSource } from "@/lib/stores/transport";

const perfSource: PlaybackSource = {
  id: "perf",
  label: "Original",
  url: "data:audio/wav;base64,perf",
  kind: "audio",
  role: "original",
};

const scoreSource: PlaybackSource = {
  id: "score",
  label: "Score rendition",
  url: "data:audio/wav;base64,score",
  kind: "audio",
  role: "score",
};

describe("deriveInspectorContext", () => {
  it("returns null when no work is loaded", () => {
    const ctx = deriveInspectorContext(null, null, 0, null, null);
    expect(ctx).toBeNull();
  });

  it("derives context with defaults when work is loaded", () => {
    const ctx = deriveInspectorContext("work-1", null, 0, null, null);
    expect(ctx).toEqual({
      workId: "work-1",
      representationId: "listen",
      currentTime: 0,
      playbackSourceId: null,
      selection: null,
    });
  });

  it("reflects the active playback source id", () => {
    const ctx = deriveInspectorContext("work-1", "score", 12.5, scoreSource, null);
    expect(ctx?.playbackSourceId).toBe("score");
    expect(ctx?.currentTime).toBe(12.5);
    expect(ctx?.representationId).toBe("score");
  });

  it("reflects the selection", () => {
    const selection: MusicalSelection = {
      timeRange: { start: 10, end: 20, domain: "performance" },
      provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
    };
    const ctx = deriveInspectorContext("work-1", "listen", 15, perfSource, selection);
    expect(ctx?.selection).toBe(selection);
  });
});

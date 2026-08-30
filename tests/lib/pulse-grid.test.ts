import { describe, expect, it } from "vitest";
import type { Insight } from "@/lib/domain.types";
import { extractObservedPulseGrid } from "@/lib/pulse-grid";

function rhythmInsight({
  id = "rhythm-1",
  versionId = "version-a",
  createdAt = "2026-08-30T20:00:00Z",
  beats = [0.12, 0.71, 1.42],
  downbeats = [0.12],
  windows,
}: {
  id?: string;
  versionId?: string;
  createdAt?: string;
  beats?: unknown;
  downbeats?: unknown;
  windows?: unknown;
} = {}): Insight {
  return {
    id,
    version_id: versionId,
    kind: "rhythm",
    claim: "test rhythm",
    evidence: {
      beats_seconds: beats,
      downbeats_seconds: downbeats,
      pulse_coordinate_unit: "seconds",
      onset_density_over_time: windows,
    },
    provenance: { engine: "beat_this", model_version: "test" },
    created_at: createdAt,
    created_by: null,
    confidence: null,
    entity_ids: [],
    produced_by_job_id: null,
    span: {
      start_beat: null,
      end_beat: null,
      start_measure: null,
      end_measure: null,
      start_seconds: null,
      end_seconds: null,
    },
  };
}

const legacyBeatWindows = [
  {
    start: 0.12,
    end: 0.71,
    density: 1,
    mode: "beat_relative",
    unit: "events_per_beat",
    coordinate_unit: "beats",
    window_size: 1,
    step_size: 1,
  },
  {
    start: 0.71,
    end: 1.42,
    density: 2,
    mode: "beat_relative",
    unit: "events_per_beat",
    coordinate_unit: "beats",
    window_size: 1,
    step_size: 1,
  },
];

describe("extractObservedPulseGrid", () => {
  it("returns the exact explicit non-uniform grid for the requested Version", () => {
    const result = extractObservedPulseGrid(
      [rhythmInsight(), rhythmInsight({ id: "other", versionId: "version-b", beats: [0, 1] })],
      "version-a",
    );

    expect(result).toEqual({
      versionId: "version-a",
      beatsSeconds: [0.12, 0.71, 1.42],
      downbeatsSeconds: [0.12],
      provenance: { engine: "beat_this", model_version: "test" },
      source: "explicit_pulse",
    });
  });

  it("preserves independently valid downbeat timestamps from the engine", () => {
    const result = extractObservedPulseGrid(
      [rhythmInsight({ downbeats: [0.2] })],
      "version-a",
    );

    expect(result?.downbeatsSeconds).toEqual([0.2]);
    expect(result?.source).toBe("explicit_pulse");
  });

  it("recovers losslessly persisted one-beat window boundaries without inventing downbeats", () => {
    const result = extractObservedPulseGrid(
      [rhythmInsight({ beats: undefined, downbeats: undefined, windows: legacyBeatWindows })],
      "version-a",
    );

    expect(result).toEqual({
      versionId: "version-a",
      beatsSeconds: [0.12, 0.71, 1.42],
      downbeatsSeconds: [],
      provenance: { engine: "beat_this", model_version: "test" },
      source: "beat_relative_windows",
    });
  });

  it("chooses the newest valid analysis without mixing Versions", () => {
    const result = extractObservedPulseGrid(
      [
        rhythmInsight({ id: "old", createdAt: "2026-08-30T19:00:00Z", beats: [0, 1, 2] }),
        rhythmInsight({ id: "new", createdAt: "2026-08-30T21:00:00Z", beats: [0.2, 0.8, 1.5] }),
      ],
      "version-a",
    );

    expect(result?.beatsSeconds).toEqual([0.2, 0.8, 1.5]);
  });

  it("fails closed on malformed explicit coordinates and non-contiguous legacy windows", () => {
    expect(
      extractObservedPulseGrid(
        [rhythmInsight({ beats: [0.2, 0.1, 0.9], windows: undefined })],
        "version-a",
      ),
    ).toBeNull();
    expect(
      extractObservedPulseGrid(
        [rhythmInsight({ beats: [0.2, Number.NaN, 0.9], windows: undefined })],
        "version-a",
      ),
    ).toBeNull();
    expect(
      extractObservedPulseGrid(
        [rhythmInsight({ downbeats: [0.4, 0.3], windows: undefined })],
        "version-a",
      ),
    ).toBeNull();
    expect(
      extractObservedPulseGrid(
        [
          rhythmInsight({
            beats: undefined,
            downbeats: undefined,
            windows: [
              legacyBeatWindows[0],
              { ...legacyBeatWindows[1], start: 0.8 },
            ],
          }),
        ],
        "version-a",
      ),
    ).toBeNull();
    expect(extractObservedPulseGrid([rhythmInsight()], "missing-version")).toBeNull();
  });
});

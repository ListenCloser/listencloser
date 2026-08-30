import { describe, expect, it } from "vitest";
import type { Insight } from "@/lib/domain.types";
import { extractObservedPulseGrid } from "@/lib/pulse-grid";

function rhythmInsight({
  id = "rhythm-1",
  versionId = "version-a",
  createdAt = "2026-08-30T20:00:00Z",
  beats = [0.12, 0.71, 1.42],
  downbeats = [0.12],
}: {
  id?: string;
  versionId?: string;
  createdAt?: string;
  beats?: unknown;
  downbeats?: unknown;
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
    },
    provenance: { engine: "beat_this", model_version: "test" },
    created_at: createdAt,
    span: {
      start_beat: null,
      end_beat: null,
      start_seconds: null,
      end_seconds: null,
    },
  } as Insight;
}

describe("extractObservedPulseGrid", () => {
  it("returns the exact non-uniform grid for the requested Version", () => {
    const result = extractObservedPulseGrid(
      [rhythmInsight(), rhythmInsight({ id: "other", versionId: "version-b", beats: [0, 1] })],
      "version-a",
    );

    expect(result).toEqual({
      versionId: "version-a",
      beatsSeconds: [0.12, 0.71, 1.42],
      downbeatsSeconds: [0.12],
      provenance: { engine: "beat_this", model_version: "test" },
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

  it("fails closed on malformed or non-monotonic coordinate evidence", () => {
    expect(
      extractObservedPulseGrid(
        [rhythmInsight({ beats: [0.2, 0.1, 0.9] })],
        "version-a",
      ),
    ).toBeNull();
    expect(
      extractObservedPulseGrid(
        [rhythmInsight({ beats: [0.2, Number.NaN, 0.9] })],
        "version-a",
      ),
    ).toBeNull();
    expect(extractObservedPulseGrid([rhythmInsight()], "missing-version")).toBeNull();
  });
});

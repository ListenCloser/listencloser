import { describe, expect, it } from "vitest";
import { deriveAvailability } from "@/lib/representation-availability";
import type { RepresentationEntry } from "@/lib/stores/workspace";

function rep(kind: RepresentationEntry["kind"]): RepresentationEntry {
  return {
    kind,
    label: kind,
    sourceUrl: "https://example.com/x",
    sourceLabel: "x",
    confidence: null,
    provenance: "test",
  };
}

describe("deriveAvailability", () => {
  it("reports original/MIDI/score/analysis independently", () => {
    const availability = deriveAvailability(
      [rep("waveform"), rep("piano_roll"), rep("score")],
      3,
    );
    expect(availability.originalAudio).toBe(true);
    expect(availability.performanceMidi).toBe(true);
    expect(availability.score).toBe(true);
    expect(availability.analysis).toBe(true);
  });

  it("reports analysis unavailable with zero insights", () => {
    const availability = deriveAvailability([rep("waveform")], 0);
    expect(availability.originalAudio).toBe(true);
    expect(availability.analysis).toBe(false);
    expect(availability.availableKinds).toEqual(["waveform"]);
  });

  it("reports all unavailable for an empty work", () => {
    const availability = deriveAvailability([], 0);
    expect(availability.originalAudio).toBe(false);
    expect(availability.performanceMidi).toBe(false);
    expect(availability.score).toBe(false);
    expect(availability.analysis).toBe(false);
    expect(availability.availableKinds).toEqual([]);
  });
});

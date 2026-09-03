import { describe, expect, it } from "vitest";
import {
  deriveAvailability,
  deriveRepresentationReadiness,
} from "@/lib/representation-availability";
import type { Job } from "@/lib/domain.types";
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

function job({
  state,
  targets,
  failedTargets = [],
}: {
  state: Job["lifecycle"]["current"];
  targets: string[];
  failedTargets?: string[];
}): Job {
  return {
    id: crypto.randomUUID(),
    workflow_id: crypto.randomUUID(),
    capability: { name: "understand", version: "1.0" },
    lifecycle: {
      current: state,
      progress: state === "running" ? 0.5 : 1,
      message: "",
      retry_count: 0,
      max_retries: 3,
      lease_expires_at: null,
      started_at: null,
      completed_at: null,
      stages: [],
    },
    input_version_ids: [],
    output_version_ids: [],
    parameters: { representation_targets: targets },
    cache_key: null,
    error: state === "failed" ? "boom" : null,
    error_details: failedTargets.length > 0
      ? { failed_representation_targets: failedTargets }
      : {},
    provenance: {},
    created_at: new Date().toISOString(),
    created_by: null,
  } as Job;
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

describe("deriveRepresentationReadiness", () => {
  it("keeps durable representations ready even when an older attempt failed", () => {
    const readiness = deriveRepresentationReadiness(
      [rep("waveform"), rep("piano_roll"), rep("score")],
      [job({ state: "failed", targets: ["piano_roll", "score"], failedTargets: ["score"] })],
    );

    expect(readiness).toEqual({
      listen: "ready",
      spectrogram: "ready",
      piano_roll: "ready",
      score: "ready",
    });
  });

  it("marks only explicitly targeted active outputs as preparing", () => {
    const readiness = deriveRepresentationReadiness(
      [rep("waveform")],
      [job({ state: "running", targets: ["piano_roll", "score"] })],
    );

    expect(readiness.listen).toBe("ready");
    expect(readiness.piano_roll).toBe("preparing");
    expect(readiness.score).toBe("preparing");
  });

  it("distinguishes a capability-specific failure from a downstream unavailable output", () => {
    const readiness = deriveRepresentationReadiness(
      [rep("waveform")],
      [job({
        state: "failed",
        targets: ["piano_roll", "score"],
        failedTargets: ["piano_roll"],
      })],
    );

    expect(readiness.listen).toBe("ready");
    expect(readiness.piano_roll).toBe("failed");
    expect(readiness.score).toBe("unavailable");
  });

  it("fails closed when a terminal failure does not identify the affected output", () => {
    const readiness = deriveRepresentationReadiness(
      [rep("waveform")],
      [job({ state: "failed", targets: ["piano_roll", "score"] })],
    );

    expect(readiness.piano_roll).toBe("unavailable");
    expect(readiness.score).toBe("unavailable");
  });

  it("lets a newer retry override an older capability-specific failure", () => {
    const failed = job({ state: "failed", targets: ["score"], failedTargets: ["score"] });
    const retry = job({ state: "running", targets: ["score"] });
    const readiness = deriveRepresentationReadiness([rep("waveform")], [retry, failed]);

    expect(readiness.score).toBe("preparing");
  });
});

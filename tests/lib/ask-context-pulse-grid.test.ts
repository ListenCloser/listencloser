import { describe, expect, it } from "vitest";
import type { Insight } from "@/lib/domain.types";
import { deriveAskContext } from "@/lib/ask/context";

function rhythmInsight(): Insight {
  return {
    id: "rhythm-1",
    version_id: "version-a",
    kind: "rhythm",
    claim: "2 notes/sec",
    evidence: {
      rhythmic_density: 2,
      beats_seconds: [0.12, 0.71, 1.42],
      downbeats_seconds: [0.12],
      pulse_coordinate_unit: "seconds",
    },
    provenance: { engine: "beat_this" },
    created_at: "2026-08-30T20:00:00Z",
    created_by: null,
    confidence: null,
    entity_ids: [],
    produced_by_job_id: null,
    span: {
      start_beat: null,
      end_beat: null,
      start_seconds: null,
      end_seconds: null,
    },
  };
}

describe("deriveAskContext pulse evidence", () => {
  it("keeps compact rhythm evidence but strips dense representation coordinates", () => {
    const source = rhythmInsight();
    const context = deriveAskContext(
      "work-a",
      "piano_roll",
      0,
      null,
      null,
      [source],
      120,
    );

    expect(context?.visibleInsights).toHaveLength(1);
    const evidence = context!.visibleInsights[0].insight.evidence;
    expect(evidence.rhythmic_density).toBe(2);
    expect(evidence.pulse_coordinate_unit).toBe("seconds");
    expect(evidence.beats_seconds).toBeUndefined();
    expect(evidence.downbeats_seconds).toBeUndefined();

    // Context derivation must not mutate the authoritative workspace evidence.
    expect(source.evidence.beats_seconds).toEqual([0.12, 0.71, 1.42]);
  });
});

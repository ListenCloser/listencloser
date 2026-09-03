import { describe, expect, it } from "vitest";
import type { WorkBundle } from "../lib/domain.types";
import { hasReusableScoreArtifacts, selectScoreArtifacts } from "../lib/score-artifacts";

function artifact(
  id: string,
  kind: string,
  versionId: string,
  parentVersionId: string | null,
  metadata: Record<string, unknown> = {},
) {
  return {
    artifact: { id, work_id: "work", kind },
    latest_version: {
      id: versionId,
      artifact_id: id,
      parent_version_id: parentVersionId,
      metadata,
    },
    versions: [],
    signed_url: `https://example.test/${versionId}`,
  };
}

function bundle(): WorkBundle {
  return {
    work: { id: "work" },
    jobs: [],
    artifacts: [
      artifact("perf-artifact", "midi_performance", "perf-v1", null),
      artifact("legacy-perf-artifact", "midi_performance", "perf-old", null),
      artifact("muse-notation", "midi_corrected", "muse-notation-v1", "perf-v1", { score_engine_requested: "musescore" }),
      artifact("muse-score", "musicxml_score", "muse-score-v1", "muse-notation-v1", { notation_midi_version_id: "muse-notation-v1" }),
      artifact("muse-audio", "rendered_score", "muse-audio-v1", "muse-notation-v1", { notation_midi_version_id: "muse-notation-v1" }),
      artifact("pm2s-notation", "midi_corrected", "pm2s-notation-v1", "perf-v1", { score_engine_requested: "pm2s" }),
      artifact("pm2s-score", "musicxml_score", "pm2s-score-v1", "pm2s-notation-v1", { score_engine_requested: "pm2s", notation_midi_version_id: "pm2s-notation-v1" }),
      artifact("pm2s-audio", "rendered_score", "pm2s-audio-v1", "pm2s-notation-v1", { notation_midi_version_id: "pm2s-notation-v1" }),
      artifact("old-pm2s-notation", "midi_corrected", "old-pm2s-notation-v1", "perf-old", { score_engine_requested: "pm2s" }),
      artifact("old-pm2s-score", "musicxml_score", "old-pm2s-score-v1", "old-pm2s-notation-v1", { score_engine_requested: "pm2s", notation_midi_version_id: "old-pm2s-notation-v1" }),
    ],
  } as unknown as WorkBundle;
}

function preLineageBundle(): WorkBundle {
  return {
    work: { id: "work" },
    jobs: [],
    artifacts: [
      artifact("perf-artifact", "midi_performance", "perf-v1", null),
      artifact("legacy-score", "musicxml_score", "legacy-score-v1", null),
      artifact("legacy-audio", "rendered_score", "legacy-audio-v1", null, {
        measure_starts_seconds: [0, 2, 4],
      }),
    ],
  } as unknown as WorkBundle;
}

describe("selectScoreArtifacts", () => {
  it("selects the requested score engine and its matching playback", () => {
    const selected = selectScoreArtifacts(bundle(), "perf-v1", "pm2s");
    expect(selected.score?.latest_version?.id).toBe("pm2s-score-v1");
    expect(selected.renderedScore?.latest_version?.id).toBe("pm2s-audio-v1");
    expect(selected.matchesPerformanceMidi).toBe(true);
  });

  it("treats lineage-backed score output without engine metadata as MuseScore", () => {
    const selected = selectScoreArtifacts(bundle(), "perf-v1", "musescore");
    expect(selected.score?.latest_version?.id).toBe("muse-score-v1");
    expect(selected.renderedScore?.latest_version?.id).toBe("muse-audio-v1");
    expect(selected.matchesPerformanceMidi).toBe(true);
  });

  it("preserves pre-lineage MuseScore display artifacts without claiming reusable lineage", () => {
    const selected = selectScoreArtifacts(preLineageBundle(), "perf-v1", "musescore");
    expect(selected.score?.latest_version?.id).toBe("legacy-score-v1");
    expect(selected.renderedScore?.latest_version?.id).toBe("legacy-audio-v1");
    expect(selected.matchesPerformanceMidi).toBe(false);
  });

  it("never exposes an untagged legacy score as PM2S", () => {
    const selected = selectScoreArtifacts(preLineageBundle(), "perf-v1", "pm2s");
    expect(selected.score).toBeUndefined();
    expect(selected.renderedScore).toBeUndefined();
    expect(selected.matchesPerformanceMidi).toBe(false);
  });

  it("does not select a tagged result derived from a different performance MIDI", () => {
    const selected = selectScoreArtifacts(bundle(), "missing-performance", "pm2s");
    expect(selected.score).toBeUndefined();
    expect(selected.renderedScore).toBeUndefined();
    expect(selected.matchesPerformanceMidi).toBe(false);
  });
});

describe("hasReusableScoreArtifacts", () => {
  it("reuses only results proven to match the exact canonical performance MIDI", () => {
    expect(hasReusableScoreArtifacts(bundle(), "perf-v1", "musescore")).toBe(true);
    expect(hasReusableScoreArtifacts(bundle(), "perf-v1", "pm2s")).toBe(true);
    expect(hasReusableScoreArtifacts(preLineageBundle(), "perf-v1", "musescore")).toBe(false);
  });
});

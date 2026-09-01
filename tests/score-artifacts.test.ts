import { describe, expect, it } from "vitest";
import type { WorkBundle } from "../lib/domain.types";
import { selectScoreArtifacts } from "../lib/score-artifacts";

function bundle(): WorkBundle {
  const artifact = (id: string, kind: string, versionId: string, parentVersionId: string | null, metadata: Record<string, unknown> = {}) => ({
    artifact: { id, work_id: "work", kind },
    latest_version: {
      id: versionId,
      artifact_id: id,
      parent_version_id: parentVersionId,
      metadata,
    },
    versions: [],
    signed_url: `https://example.test/${versionId}`,
  });

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

describe("selectScoreArtifacts", () => {
  it("selects the requested score engine and its matching playback", () => {
    const selected = selectScoreArtifacts(bundle(), "perf-v1", "pm2s");
    expect(selected.score?.latest_version?.id).toBe("pm2s-score-v1");
    expect(selected.renderedScore?.latest_version?.id).toBe("pm2s-audio-v1");
  });

  it("treats legacy score output without engine metadata as MuseScore", () => {
    const selected = selectScoreArtifacts(bundle(), "perf-v1", "musescore");
    expect(selected.score?.latest_version?.id).toBe("muse-score-v1");
    expect(selected.renderedScore?.latest_version?.id).toBe("muse-audio-v1");
  });

  it("does not select a result derived from a different performance MIDI", () => {
    const selected = selectScoreArtifacts(bundle(), "missing-performance", "pm2s");
    expect(selected.score).toBeUndefined();
    expect(selected.renderedScore).toBeUndefined();
  });
});

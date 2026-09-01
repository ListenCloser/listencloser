import { describe, expect, it } from "vitest";
import type { WorkArtifactBundle } from "@/lib/domain.types";
import { performanceMidiVersionId, selectScoreArtifacts } from "@/lib/score-artifacts";

function bundle(
  kind: string,
  versionId: string,
  metadata: Record<string, unknown> = {},
  signedUrl = `https://example.test/${versionId}`,
): WorkArtifactBundle {
  return {
    artifact: { kind },
    latest_version: { id: versionId, metadata },
    versions: [],
    signed_url: signedUrl,
  } as unknown as WorkArtifactBundle;
}

describe("selectScoreArtifacts", () => {
  it("selects the requested engine instead of whichever score is newest", () => {
    const artifacts = [
      bundle("musicxml_score", "pm2s-xml", {
        score_engine_requested: "pm2s",
        notation_midi_version_id: "pm2s-midi",
      }),
      bundle("musicxml_score", "muse-xml", {
        score_engine_requested: "musescore",
        notation_midi_version_id: "muse-midi",
      }),
    ];

    expect(selectScoreArtifacts(artifacts, "musescore").score?.latest_version?.id).toBe("muse-xml");
    expect(selectScoreArtifacts(artifacts, "pm2s").score?.latest_version?.id).toBe("pm2s-xml");
  });

  it("pairs rendered score by notation MIDI identity", () => {
    const artifacts = [
      bundle("musicxml_score", "pm2s-xml", {
        score_engine_requested: "pm2s",
        notation_midi_version_id: "pm2s-midi",
      }),
      bundle("rendered_score", "wrong-render", { notation_midi_version_id: "muse-midi" }),
      bundle("rendered_score", "pm2s-render", { notation_midi_version_id: "pm2s-midi" }),
    ];

    expect(selectScoreArtifacts(artifacts, "pm2s").renderedScore?.latest_version?.id).toBe("pm2s-render");
  });

  it("treats legacy untagged score artifacts as the MuseScore baseline", () => {
    const legacy = bundle("musicxml_score", "legacy-xml", {
      notation_midi_version_id: "legacy-midi",
    });

    expect(selectScoreArtifacts([legacy], "musescore").score?.latest_version?.id).toBe("legacy-xml");
    expect(selectScoreArtifacts([legacy], "pm2s").score).toBeNull();
  });

  it("does not fall back to another engine when the requested score is missing", () => {
    const muse = bundle("musicxml_score", "muse-xml", {
      score_engine_requested: "musescore",
      notation_midi_version_id: "muse-midi",
    });

    expect(selectScoreArtifacts([muse], "pm2s")).toEqual({ score: null, renderedScore: null });
  });
});

describe("performanceMidiVersionId", () => {
  it("returns only canonical performance MIDI and ignores score/corrected MIDI", () => {
    expect(performanceMidiVersionId([
      bundle("midi_corrected", "score-midi"),
      bundle("midi_performance", "performance-midi"),
    ])).toBe("performance-midi");
    expect(performanceMidiVersionId([bundle("midi_corrected", "score-midi")])).toBeNull();
  });
});

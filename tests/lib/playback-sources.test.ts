import { describe, expect, it } from "vitest";
import { buildPlaybackSources } from "@/lib/playback-sources";

const ref = (id: string) => ({ id, url: `https://example.com/${id}` });

describe("buildPlaybackSources", () => {
  it("offers Original, Transcription, and Score as distinct sources", () => {
    const { sources } = buildPlaybackSources({
      original: ref("orig"),
      transcription: ref("trans"),
      extraTakes: [],
      score: ref("score"),
    });
    expect(sources.map((s) => s.role)).toEqual(["original", "transcription", "score"]);
    expect(sources.map((s) => s.label)).toEqual(["Original", "Transcription", "Score"]);
  });

  it("derives the Score source from the score artifact, not the transcription", () => {
    const { sources } = buildPlaybackSources({
      original: null,
      transcription: ref("trans"),
      extraTakes: [],
      score: ref("score-audio"),
    });
    const score = sources.find((s) => s.role === "score");
    expect(score?.url).toBe("https://example.com/score-audio");
    expect(score?.id).toBe("score-audio");
  });

  it("omits the Score source when no score playback exists", () => {
    const { sources } = buildPlaybackSources({
      original: ref("orig"),
      transcription: ref("trans"),
      extraTakes: [],
      score: null,
    });
    expect(sources.some((s) => s.role === "score")).toBe(false);
  });

  it("does not silently substitute the transcription for the score", () => {
    const { sources } = buildPlaybackSources({
      original: ref("orig"),
      transcription: ref("trans"),
      extraTakes: [],
      score: null,
    });
    expect(sources.find((s) => s.role === "score")).toBeUndefined();
    expect(sources.find((s) => s.role === "transcription")?.url).toBe("https://example.com/trans");
  });

  it("defaults the active source to transcription, falling back to original", () => {
    expect(
      buildPlaybackSources({ original: ref("o"), transcription: ref("t"), extraTakes: [], score: ref("s") }).activeId,
    ).toBe("t");
    expect(
      buildPlaybackSources({ original: ref("o"), transcription: null, extraTakes: [], score: null }).activeId,
    ).toBe("o");
    expect(
      buildPlaybackSources({ original: null, transcription: null, extraTakes: [], score: null }).activeId,
    ).toBeNull();
  });
});

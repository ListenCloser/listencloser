import { describe, expect, it } from "vitest";
import type { WorkBundle } from "../lib/domain.types";
import {
  defaultScoreSourceVersionId,
  scoreSourceOptions,
  selectScoreSource,
} from "../lib/score-sources";

function artifact(
  id: string,
  kind: string,
  versionId: string,
  metadata: Record<string, unknown> = {},
  label = "",
  signedUrl: string | null = `https://example.test/${versionId}`,
) {
  return {
    artifact: { id, work_id: "work", kind },
    latest_version: {
      id: versionId,
      artifact_id: id,
      parent_version_id: null,
      label,
      metadata,
    },
    versions: [],
    signed_url: signedUrl,
  };
}

function bundle(artifacts: ReturnType<typeof artifact>[]): WorkBundle {
  return {
    work: { id: "work" },
    jobs: [],
    artifacts,
  } as unknown as WorkBundle;
}

describe("scoreSourceOptions", () => {
  it("exposes only signed first-class score_source versions", () => {
    const options = scoreSourceOptions(bundle([
      artifact("source", "musicxml_score", "source-v1", {
        representation: "score_source",
        original_filename: "composer.musicxml",
      }),
      artifact("generated", "musicxml_score", "generated-v1", {
        representation: "notation_draft",
        score_engine_requested: "musescore",
      }),
      artifact("unsigned", "musicxml_score", "unsigned-v1", {
        representation: "score_source",
        original_filename: "hidden.musicxml",
      }, "", null),
    ]));

    expect(options).toEqual([
      { versionId: "source-v1", label: "Attached · composer.musicxml" },
    ]);
  });

  it("keeps multiple sources explicit without granting recency authority", () => {
    const options = scoreSourceOptions(bundle([
      artifact("second", "musicxml_score", "v2", {
        representation: "score_source",
        original_filename: "same.musicxml",
      }),
      artifact("first", "musicxml_score", "v1", {
        representation: "score_source",
        original_filename: "same.musicxml",
      }),
    ]));

    expect(options).toEqual([
      { versionId: "v1", label: "Attached · same.musicxml (1)" },
      { versionId: "v2", label: "Attached · same.musicxml (2)" },
    ]);
    expect(defaultScoreSourceVersionId(options)).toBeNull();
  });

  it("defaults only when exactly one source is unambiguous", () => {
    expect(defaultScoreSourceVersionId([])).toBeNull();
    expect(defaultScoreSourceVersionId([
      { versionId: "source-v1", label: "Attached · score.musicxml" },
    ])).toBe("source-v1");
  });
});

describe("selectScoreSource", () => {
  it("selects by exact immutable Version id and never falls back by kind", () => {
    const work = bundle([
      artifact("a", "musicxml_score", "source-v1", {
        representation: "score_source",
      }, "one.musicxml"),
      artifact("b", "musicxml_score", "source-v2", {
        representation: "score_source",
      }, "two.musicxml"),
    ]);

    expect(selectScoreSource(work, "source-v2")?.latest_version?.id).toBe("source-v2");
    expect(selectScoreSource(work, "missing")).toBeUndefined();
    expect(selectScoreSource(work, null)).toBeUndefined();
  });
});

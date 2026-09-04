import { describe, expect, it } from "vitest";

import type { WorkBundle } from "../lib/domain.types";
import { originalPlaybackSource, selectLayerSources } from "../lib/layers";

function artifact(
  id: string,
  kind: string,
  versionId: string,
  metadata: Record<string, unknown> = {},
) {
  return {
    artifact: { id, work_id: "work", kind },
    latest_version: {
      id: versionId,
      artifact_id: id,
      parent_version_id: null,
      metadata,
    },
    versions: [],
    signed_url: `https://example.test/${versionId}`,
  };
}

function stem(
  role: string,
  versionId: string,
  sourceVersionId = "original-v1",
  separationJobId = "job-1",
) {
  return artifact(`artifact-${versionId}`, "stems", versionId, {
    representation: "source_stem",
    source_version_id: sourceVersionId,
    separation_job_id: separationJobId,
    stem_role: role,
  });
}

function bundle(artifacts: unknown[]): WorkBundle {
  return {
    work: { id: "work" },
    jobs: [],
    artifacts,
  } as unknown as WorkBundle;
}

describe("experimental layer source authority", () => {
  it("keeps Original as the explicit normal playback source", () => {
    const work = bundle([
      artifact("original", "audio_original", "original-v1"),
      artifact("rendered", "audio_rendered", "rendered-v1"),
    ]);

    expect(originalPlaybackSource(work)).toEqual({
      id: "original-v1",
      label: "Original",
      role: "original",
      kind: "audio",
      url: "https://example.test/original-v1",
    });
  });

  it("exposes exactly vocals, drums, bass, other when one job produced a complete set", () => {
    const work = bundle([
      artifact("original", "audio_original", "original-v1"),
      stem("vocals", "vocals-v1"),
      stem("drums", "drums-v1"),
      stem("bass", "bass-v1"),
      stem("other", "other-v1"),
    ]);

    const layers = selectLayerSources(work, "original-v1");
    expect(layers.map((layer) => layer.label)).toEqual(["Vocals", "Drums", "Bass", "Other"]);
    expect(layers.every((layer) => layer.role === "derived")).toBe(true);
    expect(layers.every((layer) => layer.sourceVersionId === "original-v1")).toBe(true);
  });

  it("hides partial output from a failed separation job", () => {
    const work = bundle([
      artifact("original", "audio_original", "original-v1"),
      stem("vocals", "vocals-partial", "original-v1", "failed-job"),
      stem("drums", "drums-partial", "original-v1", "failed-job"),
    ]);

    expect(selectLayerSources(work, "original-v1")).toEqual([]);
  });

  it("never mixes roles across jobs or source Versions to manufacture a complete result", () => {
    const work = bundle([
      artifact("original", "audio_original", "original-v2"),
      stem("vocals", "vocals-a", "original-v2", "job-a"),
      stem("drums", "drums-a", "original-v2", "job-a"),
      stem("bass", "bass-b", "original-v2", "job-b"),
      stem("other", "other-b", "original-v2", "job-b"),
      stem("bass", "bass-old", "original-v1", "job-a"),
      stem("other", "other-old", "original-v1", "job-a"),
    ]);

    expect(selectLayerSources(work, "original-v2")).toEqual([]);
  });
});

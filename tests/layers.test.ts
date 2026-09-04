import { describe, expect, it } from "vitest";

import type { WorkBundle } from "../lib/domain.types";
import {
  completeLayerJobIds,
  originalPlaybackSource,
  selectLayerSources,
} from "../lib/layers";

function artifact(
  id: string,
  kind: string,
  versionId: string,
  {
    parentVersionId = null,
    producedByJobId = null,
    metadata = {},
  }: {
    parentVersionId?: string | null;
    producedByJobId?: string | null;
    metadata?: Record<string, unknown>;
  } = {},
) {
  return {
    artifact: { id, work_id: "work", kind },
    latest_version: {
      id: versionId,
      artifact_id: id,
      parent_version_id: parentVersionId,
      produced_by_job_id: producedByJobId,
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
  metadata: Record<string, unknown> = {},
) {
  return artifact(`artifact-${versionId}`, "stems", versionId, {
    parentVersionId: sourceVersionId,
    producedByJobId: separationJobId,
    metadata: {
      representation: "source_stem",
      stem_role: role,
      ...metadata,
    },
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

  it("exposes exactly vocals, drums, bass, other for one succeeded complete job", () => {
    const work = bundle([
      artifact("original", "audio_original", "original-v1"),
      stem("vocals", "vocals-v1"),
      stem("drums", "drums-v1"),
      stem("bass", "bass-v1"),
      stem("other", "other-v1"),
    ]);

    expect(completeLayerJobIds(work, "original-v1")).toEqual(["job-1"]);
    const layers = selectLayerSources(work, "original-v1", new Set(["job-1"]));
    expect(layers.map((layer) => layer.label)).toEqual(["Vocals", "Drums", "Bass", "Other"]);
    expect(layers.every((layer) => layer.role === "derived")).toBe(true);
    expect(layers.every((layer) => layer.sourceVersionId === "original-v1")).toBe(true);
    expect(layers.every((layer) => layer.separationJobId === "job-1")).toBe(true);
  });

  it("does not expose a complete artifact set unless its exact Job succeeded", () => {
    const work = bundle([
      stem("vocals", "vocals-failed", "original-v1", "failed-job"),
      stem("drums", "drums-failed", "original-v1", "failed-job"),
      stem("bass", "bass-failed", "original-v1", "failed-job"),
      stem("other", "other-failed", "original-v1", "failed-job"),
    ]);

    expect(completeLayerJobIds(work, "original-v1")).toEqual(["failed-job"]);
    expect(selectLayerSources(work, "original-v1", new Set())).toEqual([]);
  });

  it("hides partial output even when its producing Job later has a succeeded state", () => {
    const work = bundle([
      stem("vocals", "vocals-partial", "original-v1", "job-1"),
      stem("drums", "drums-partial", "original-v1", "job-1"),
    ]);

    expect(completeLayerJobIds(work, "original-v1")).toEqual([]);
    expect(selectLayerSources(work, "original-v1", new Set(["job-1"]))).toEqual([]);
  });

  it("never mixes roles across Jobs or source Versions to manufacture a complete result", () => {
    const work = bundle([
      artifact("original", "audio_original", "original-v2"),
      stem("vocals", "vocals-a", "original-v2", "job-a"),
      stem("drums", "drums-a", "original-v2", "job-a"),
      stem("bass", "bass-b", "original-v2", "job-b"),
      stem("other", "other-b", "original-v2", "job-b"),
      stem("bass", "bass-old", "original-v1", "job-a"),
      stem("other", "other-old", "original-v1", "job-a"),
    ]);

    expect(completeLayerJobIds(work, "original-v2")).toEqual([]);
    expect(
      selectLayerSources(work, "original-v2", new Set(["job-a", "job-b"])),
    ).toEqual([]);
  });

  it("uses structural Version lineage instead of duplicate metadata claims", () => {
    const misleading = {
      source_version_id: "wrong-source",
      separation_job_id: "wrong-job",
    };
    const work = bundle([
      stem("vocals", "vocals-v1", "original-v1", "job-1", misleading),
      stem("drums", "drums-v1", "original-v1", "job-1", misleading),
      stem("bass", "bass-v1", "original-v1", "job-1", misleading),
      stem("other", "other-v1", "original-v1", "job-1", misleading),
    ]);

    const layers = selectLayerSources(work, "original-v1", new Set(["job-1"]));
    expect(layers).toHaveLength(4);
    expect(layers.every((layer) => layer.sourceVersionId === "original-v1")).toBe(true);
    expect(layers.every((layer) => layer.separationJobId === "job-1")).toBe(true);
  });
});

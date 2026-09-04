import type { components } from "./api-types";
import { clearWorkDataCache } from "./api-client";
import type { WorkBundle } from "./domain.types";
import { openapiClient, requireOpenApiData } from "./openapi-client";
import type { PlaybackSource } from "./stores/transport";

export const LAYER_ROLES = ["vocals", "drums", "bass", "other"] as const;
export type LayerRole = (typeof LAYER_ROLES)[number];

export type LayerPlaybackSource = PlaybackSource & {
  layerRole: LayerRole;
  sourceVersionId: string;
  separationJobId: string;
};

type WorkflowJobResponse = components["schemas"]["WorkflowJobResponse"];

function isLayerRole(value: unknown): value is LayerRole {
  return typeof value === "string" && LAYER_ROLES.includes(value as LayerRole);
}

export function originalPlaybackSource(bundle: WorkBundle): PlaybackSource | null {
  const original = bundle.artifacts.find(
    (item) => item.artifact.kind === "audio_original" && item.latest_version && item.signed_url,
  );
  if (!original?.latest_version || !original.signed_url) return null;
  return {
    id: original.latest_version.id,
    label: "Original",
    role: "original",
    kind: "audio",
    url: original.signed_url,
  };
}

/**
 * Select only a complete four-role separation result for the current source
 * Version. A failed job may have persisted one or more partial outputs before a
 * database/storage error; those are intentionally not product-visible.
 */
export function selectLayerSources(
  bundle: WorkBundle,
  sourceVersionId: string,
): LayerPlaybackSource[] {
  const groups = new Map<string, Map<LayerRole, LayerPlaybackSource>>();

  for (const item of bundle.artifacts) {
    if (item.artifact.kind !== "stems" || !item.latest_version || !item.signed_url) continue;
    const metadata = item.latest_version.metadata as Record<string, unknown>;
    if (metadata.source_version_id !== sourceVersionId) continue;
    const role = metadata.stem_role;
    const separationJobId = metadata.separation_job_id;
    if (!isLayerRole(role) || typeof separationJobId !== "string") continue;

    let group = groups.get(separationJobId);
    if (!group) {
      group = new Map();
      groups.set(separationJobId, group);
    }
    // Work bundles are newest-first. Keep the first Version for a role if a
    // malformed/legacy bundle ever contains duplicates from one job.
    if (!group.has(role)) {
      group.set(role, {
        id: item.latest_version.id,
        label: role[0].toUpperCase() + role.slice(1),
        role: "derived",
        kind: "audio",
        url: item.signed_url,
        layerRole: role,
        sourceVersionId,
        separationJobId,
      });
    }
  }

  for (const group of groups.values()) {
    if (LAYER_ROLES.every((role) => group.has(role))) {
      return LAYER_ROLES.map((role) => group.get(role)!);
    }
  }
  return [];
}

export async function startLayerSeparation(
  versionId: string,
  projectId: string,
): Promise<WorkflowJobResponse> {
  const result = await openapiClient.POST("/api/v1/workflows/create", {
    body: {
      version_id: versionId,
      project_id: projectId,
      action: "separate",
      // Model, checkpoint and inference parameters are server-authoritative.
      // The public action deliberately cannot select arbitrary model weights.
      parameters: {},
    },
  });
  return requireOpenApiData(result);
}

export function invalidateLayerWork(): void {
  // The optional workflow is intentionally detached from the Work processing
  // job list, so explicitly refresh the immutable Work graph after completion.
  clearWorkDataCache();
}

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
type LayerGroup = Map<LayerRole, LayerPlaybackSource>;

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

function layerGroups(bundle: WorkBundle, sourceVersionId: string): Map<string, LayerGroup> {
  const groups = new Map<string, LayerGroup>();

  for (const item of bundle.artifacts) {
    if (item.artifact.kind !== "stems" || !item.latest_version || !item.signed_url) continue;
    const version = item.latest_version;
    // Source and producing Job are already authoritative Version fields. Do not
    // trust duplicate JSON metadata for lineage.
    if (version.parent_version_id !== sourceVersionId) continue;
    const separationJobId = version.produced_by_job_id;
    if (typeof separationJobId !== "string" || separationJobId.length === 0) continue;

    const metadata = version.metadata as Record<string, unknown>;
    const role = metadata.stem_role;
    if (!isLayerRole(role)) continue;

    let group = groups.get(separationJobId);
    if (!group) {
      group = new Map();
      groups.set(separationJobId, group);
    }
    // Work bundles are newest-first. Keep the first Version for a role if a
    // malformed/legacy graph ever contains duplicate stem artifacts from the
    // same successful run.
    if (!group.has(role)) {
      group.set(role, {
        id: version.id,
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

  return groups;
}

/** Return only Job IDs that structurally own a complete four-role candidate set. */
export function completeLayerJobIds(bundle: WorkBundle, sourceVersionId: string): string[] {
  return [...layerGroups(bundle, sourceVersionId).entries()]
    .filter(([, group]) => LAYER_ROLES.every((role) => group.has(role)))
    .map(([jobId]) => jobId);
}

/**
 * Select one coherent, complete four-role result for the current source Version.
 *
 * Read paths must additionally prove that the producing durable Job succeeded.
 * This prevents a failed job that happened to persist four artifacts before its
 * terminal bookkeeping step from becoming product-visible, and it prevents
 * mixing different Jobs, source Versions, or partial retries.
 */
export function selectLayerSources(
  bundle: WorkBundle,
  sourceVersionId: string,
  succeededSeparationJobIds: ReadonlySet<string>,
): LayerPlaybackSource[] {
  const groups = layerGroups(bundle, sourceVersionId);
  for (const [jobId, group] of groups) {
    if (!succeededSeparationJobIds.has(jobId)) continue;
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

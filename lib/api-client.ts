import { apiFetch } from "./api";
import type { components } from "./api-types";
import { openapiClient, requireOpenApiData } from "./openapi-client";
import { getQueryClient } from "./query-client";
import { supabase } from "./supabase";
import type {
  Project,
  Work,
  Artifact,
  Version,
  Workflow,
  Job,
  Entity,
  Insight,
  JobStatus,
  VersionResource,
  WorkBundle,
} from "./domain.types";

type ApiProject = components["schemas"]["Project"];
type ApiWork = components["schemas"]["Work"];
type ApiArtifact = components["schemas"]["Artifact"];
type ApiVersion = components["schemas"]["Version"];
type ApiVersionResource = components["schemas"]["VersionResourceResponse"];

type UploadIntent = {
  bucket: string;
  storage_key: string;
  token: string;
  max_bytes: number;
};

function assertProjectResponse(value: ApiProject): asserts value is Project {
  for (const field of ["id", "description", "created_at", "updated_at", "archived_at"] as const) {
    if (value[field] === undefined) {
      throw new Error(`Invalid Project response: missing server field "${field}"`);
    }
  }
}

function normalizeProject(value: ApiProject): Project {
  assertProjectResponse(value);
  return value;
}

function assertWorkResponse(value: ApiWork): asserts value is Work {
  for (const field of ["id", "composer", "created_at", "updated_at"] as const) {
    if (value[field] === undefined) {
      throw new Error(`Invalid Work response: missing server field "${field}"`);
    }
  }
}

function normalizeWork(value: ApiWork): Work {
  assertWorkResponse(value);
  return value;
}

function assertArtifactResponse(value: ApiArtifact): asserts value is Artifact {
  for (const field of ["id", "created_at"] as const) {
    if (value[field] === undefined) {
      throw new Error(`Invalid Artifact response: missing server field "${field}"`);
    }
  }
}

function normalizeArtifact(value: ApiArtifact): Artifact {
  assertArtifactResponse(value);
  return value;
}

function assertVersionResponse(value: ApiVersion): asserts value is Version {
  for (const field of [
    "id",
    "parent_version_id",
    "lineage",
    "byte_size",
    "sha256",
    "created_at",
    "created_by",
    "produced_by_job_id",
    "metadata",
  ] as const) {
    if (value[field] === undefined) {
      throw new Error(`Invalid Version response: missing server field "${field}"`);
    }
  }
}

function normalizeVersion(value: ApiVersion): Version {
  assertVersionResponse(value);
  return value;
}

function normalizeVersionResource(value: ApiVersionResource): VersionResource {
  return {
    artifact: normalizeArtifact(value.artifact),
    version: normalizeVersion(value.version),
    signed_url: value.signed_url,
  };
}

const WORK_CACHE_TTL_MS = 5 * 60 * 1000;

const workDataMetaKeys = {
  epoch: ["work-data-meta", "epoch"] as const,
  workRevision: (epoch: number, workId: string) => ["work-data-meta", epoch, "work-revision", workId] as const,
  versionRevision: (epoch: number, versionId: string) => ["work-data-meta", epoch, "version-revision", versionId] as const,
  versionOwner: (epoch: number, versionId: string) => ["work-data-meta", epoch, "version-owner", versionId] as const,
};

const workDataKeys = {
  work: (epoch: number, workId: string, revision: number) => ["work-data", epoch, "work", workId, revision] as const,
  entities: (epoch: number, versionId: string, revision: number) => ["work-data", epoch, "version", versionId, "entities", revision] as const,
  insights: (epoch: number, versionId: string, revision: number) => ["work-data", epoch, "version", versionId, "insights", revision] as const,
};

function cacheEpoch(): number {
  return getQueryClient().getQueryData<number>(workDataMetaKeys.epoch) ?? 0;
}

function workRevision(epoch: number, workId: string): number {
  return getQueryClient().getQueryData<number>(workDataMetaKeys.workRevision(epoch, workId)) ?? 0;
}

function versionRevision(epoch: number, versionId: string): number {
  return getQueryClient().getQueryData<number>(workDataMetaKeys.versionRevision(epoch, versionId)) ?? 0;
}

function bumpWorkRevision(epoch: number, workId: string): void {
  const queryClient = getQueryClient();
  queryClient.setQueryData(workDataMetaKeys.workRevision(epoch, workId), workRevision(epoch, workId) + 1);
}

function bumpVersionRevision(epoch: number, versionId: string): void {
  const queryClient = getQueryClient();
  queryClient.setQueryData(
    workDataMetaKeys.versionRevision(epoch, versionId),
    versionRevision(epoch, versionId) + 1,
  );
}

function hasActiveJob(bundle: WorkBundle): boolean {
  return bundle.jobs.some((job) => ["queued", "claimed", "running"].includes(job.lifecycle.current));
}

function allVersionIds(bundle: WorkBundle): string[] {
  const ids = new Set<string>();
  for (const item of bundle.artifacts) {
    for (const version of item.versions) ids.add(version.id);
    if (item.latest_version) ids.add(item.latest_version.id);
  }
  return [...ids];
}

function indexBundle(epoch: number, bundle: WorkBundle): void {
  const queryClient = getQueryClient();
  for (const versionId of allVersionIds(bundle)) {
    queryClient.setQueryData(workDataMetaKeys.versionOwner(epoch, versionId), bundle.work.id);
  }
}

function currentMidiVersionId(bundle: WorkBundle): string | null {
  const performance = bundle.artifacts.find(
    (item) => item.artifact.kind === "midi_performance" && item.latest_version,
  );
  if (performance?.latest_version) return performance.latest_version.id;
  const corrected = bundle.artifacts.find(
    (item) => item.artifact.kind === "midi_corrected" && item.latest_version,
  );
  return corrected?.latest_version?.id ?? null;
}

function invalidateVersionData(epoch: number, versionId: string): void {
  bumpVersionRevision(epoch, versionId);
}

function invalidateWorkCache(epoch: number, workId: string): void {
  const queryClient = getQueryClient();
  const revision = workRevision(epoch, workId);
  const bundle = queryClient.getQueryData<WorkBundle>(workDataKeys.work(epoch, workId, revision));

  bumpWorkRevision(epoch, workId);
  if (bundle) {
    for (const versionId of allVersionIds(bundle)) invalidateVersionData(epoch, versionId);
  }
}

function invalidateVersionWorks(versionIds: readonly string[]): void {
  const epoch = cacheEpoch();
  const queryClient = getQueryClient();
  const workIds = new Set<string>();

  for (const versionId of new Set(versionIds)) {
    const workId = queryClient.getQueryData<string>(workDataMetaKeys.versionOwner(epoch, versionId));
    if (workId) workIds.add(workId);
  }

  for (const workId of workIds) invalidateWorkCache(epoch, workId);
  // Always advance the triggering version keys. This also handles freshly
  // uploaded versions whose owning Work bundle has not resolved yet.
  for (const versionId of new Set(versionIds)) invalidateVersionData(epoch, versionId);
}

async function mutateVersionWorks<T>(
  versionIds: readonly string[],
  mutation: () => Promise<T>,
): Promise<T> {
  // Revision bumps are synchronous. A read that starts after this call gets a
  // fresh TanStack key immediately, while any older caller may still resolve
  // harmlessly against its previous key. A successful commit advances the keys
  // again so reads started during the mutation cannot become post-commit state.
  invalidateVersionWorks(versionIds);
  const result = await mutation();
  invalidateVersionWorks(versionIds);
  return result;
}

export function clearWorkDataCache(): void {
  const queryClient = getQueryClient();
  queryClient.setQueryData(workDataMetaKeys.epoch, cacheEpoch() + 1);
}

export async function createProject(name: string, description?: string): Promise<Project> {
  const result = await openapiClient.POST("/api/v1/projects", {
    body: { name, description: description ?? "" },
  });
  return normalizeProject(requireOpenApiData(result));
}

export async function listProjects(): Promise<Project[]> {
  const result = await openapiClient.GET("/api/v1/projects");
  return requireOpenApiData(result).map(normalizeProject);
}

export async function createWork(projectId: string, title: string, composer?: string): Promise<Work> {
  const result = await openapiClient.POST("/api/v1/projects/{project_id}/works", {
    params: { path: { project_id: projectId } },
    body: { title, composer: composer ?? null },
  });
  return normalizeWork(requireOpenApiData(result));
}

export async function listWorks(projectId: string): Promise<Work[]> {
  const result = await openapiClient.GET("/api/v1/projects/{project_id}/works", {
    params: { path: { project_id: projectId } },
  });
  return requireOpenApiData(result).map(normalizeWork);
}

export async function getWorkBundle(workId: string): Promise<WorkBundle> {
  const queryClient = getQueryClient();
  const epoch = cacheEpoch();
  const revision = workRevision(epoch, workId);
  const bundle = await queryClient.fetchQuery({
    queryKey: workDataKeys.work(epoch, workId, revision),
    queryFn: () => apiFetch<WorkBundle>(`/api/v1/works/${workId}`),
    staleTime: WORK_CACHE_TTL_MS,
  });

  // The request may have become stale while it was in flight. Its caller still
  // receives the response, but it must not mutate ownership or child-evidence
  // state for the newer revision.
  if (epoch !== cacheEpoch() || revision !== workRevision(epoch, workId)) return bundle;

  indexBundle(epoch, bundle);
  const midiVersionId = currentMidiVersionId(bundle);
  if (hasActiveJob(bundle)) {
    // Processing changes the durable Work over time. Advance the revision after
    // every active snapshot so the existing page poll necessarily hits the
    // server again instead of treating that snapshot as terminal cache state.
    bumpWorkRevision(epoch, workId);
    if (midiVersionId) invalidateVersionData(epoch, midiVersionId);
  } else if (midiVersionId) {
    // Warm immutable child evidence, but never make it part of the Work-open
    // critical path. HomeContent can expose durable audio as soon as the bundle
    // arrives, while its foreground child reads deduplicate against these same
    // TanStack keys if the warm-up is still in flight.
    void Promise.allSettled([getEntities(midiVersionId), getInsights(midiVersionId)]);
  }

  return bundle;
}

export async function deleteWork(workId: string): Promise<{ deleted: string }> {
  const result = await apiFetch<{ deleted: string }>(`/api/v1/works/${workId}`, {
    method: "DELETE",
  });
  invalidateWorkCache(cacheEpoch(), workId);
  return result;
}

function rememberUploadedVersion(result: { artifact: Artifact; version: Version }): { artifact: Artifact; version: Version } {
  const epoch = cacheEpoch();
  const queryClient = getQueryClient();
  invalidateWorkCache(epoch, result.artifact.work_id);
  // Version ownership is immutable and is needed before a Work bundle that
  // contains the new version has had a chance to resolve.
  queryClient.setQueryData(
    workDataMetaKeys.versionOwner(epoch, result.version.id),
    result.artifact.work_id,
  );
  return result;
}

export async function uploadArtifact(
  projectId: string,
  file: File,
  workId?: string,
): Promise<{ artifact: Artifact; version: Version }> {
  if (workId) invalidateWorkCache(cacheEpoch(), workId);
  if (!supabase) throw new Error("Supabase storage is not configured");

  const descriptor = {
    filename: file.name,
    byte_size: file.size,
    content_type: file.type || null,
    work_id: workId ?? null,
  };
  const intent = await apiFetch<UploadIntent>(
    `/api/v1/projects/${projectId}/artifacts/upload-intent`,
    {
      method: "POST",
      body: JSON.stringify(descriptor),
    },
  );

  if (file.size > intent.max_bytes) {
    throw new Error("File exceeds upload size limit");
  }

  const { error: uploadError } = await supabase.storage
    .from(intent.bucket)
    .uploadToSignedUrl(intent.storage_key, intent.token, file);
  if (uploadError) {
    throw new Error(`Storage upload failed: ${uploadError.message}`);
  }

  const result = await apiFetch<{ artifact: Artifact; version: Version }>(
    `/api/v1/projects/${projectId}/artifacts/finalize-upload`,
    {
      method: "POST",
      body: JSON.stringify({
        ...descriptor,
        storage_key: intent.storage_key,
      }),
    },
  );
  return rememberUploadedVersion(result);
}

export async function startUnderstandWorkflow(
  versionId: string,
  projectId: string,
  transcriptionProfile?: string,
): Promise<{ workflow: Workflow; job: Job }> {
  return mutateVersionWorks([versionId], () =>
    apiFetch<{ workflow: Workflow; job: Job }>("/api/v1/workflows/understand", {
      method: "POST",
      body: JSON.stringify({
        version_id: versionId,
        project_id: projectId,
        ...(transcriptionProfile ? { transcription_profile: transcriptionProfile } : {}),
      }),
    }),
  );
}

export async function startVariationWorkflow(
  versionId: string,
  projectId: string,
  transposeSemitones: number,
): Promise<{ workflow: Workflow; job: Job }> {
  return mutateVersionWorks([versionId], () =>
    apiFetch<{ workflow: Workflow; job: Job }>("/api/v1/workflows/variation", {
      method: "POST",
      body: JSON.stringify({
        version_id: versionId,
        project_id: projectId,
        transpose_semitones: transposeSemitones,
      }),
    }),
  );
}

export async function startCompareWorkflow(
  versionIdA: string,
  versionIdB: string,
  projectId: string,
): Promise<{ workflow: Workflow; job: Job }> {
  return mutateVersionWorks([versionIdA, versionIdB], () =>
    apiFetch<{ workflow: Workflow; job: Job }>("/api/v1/workflows/compare", {
      method: "POST",
      body: JSON.stringify({
        version_id_a: versionIdA,
        version_id_b: versionIdB,
        project_id: projectId,
      }),
    }),
  );
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return apiFetch<JobStatus>(`/api/v1/jobs/${jobId}`);
}

export async function cancelJob(jobId: string): Promise<JobStatus> {
  const result = await apiFetch<JobStatus>(`/api/v1/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  clearWorkDataCache();
  return result;
}

export async function retryJob(jobId: string): Promise<JobStatus> {
  clearWorkDataCache();
  return apiFetch<JobStatus>(`/api/v1/jobs/${jobId}/retry`, {
    method: "POST",
  });
}

export async function getVersionResource(versionId: string): Promise<VersionResource> {
  const result = await openapiClient.GET("/api/v1/versions/{version_id}", {
    params: { path: { version_id: versionId } },
  });
  return normalizeVersionResource(requireOpenApiData(result));
}

export async function getEntities(versionId: string): Promise<Entity[]> {
  const epoch = cacheEpoch();
  const revision = versionRevision(epoch, versionId);
  return getQueryClient().fetchQuery({
    queryKey: workDataKeys.entities(epoch, versionId, revision),
    queryFn: () => apiFetch<Entity[]>(`/api/v1/versions/${versionId}/entities`),
    staleTime: WORK_CACHE_TTL_MS,
  });
}

export async function getInsights(versionId: string): Promise<Insight[]> {
  const epoch = cacheEpoch();
  const revision = versionRevision(epoch, versionId);
  return getQueryClient().fetchQuery({
    queryKey: workDataKeys.insights(epoch, versionId, revision),
    queryFn: () => apiFetch<Insight[]>(`/api/v1/versions/${versionId}/insights`),
    staleTime: WORK_CACHE_TTL_MS,
  });
}

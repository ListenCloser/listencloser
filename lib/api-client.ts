import type { QueryKey } from "@tanstack/react-query";

import { apiFetch } from "./api";
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

type UploadIntent = {
  bucket: string;
  storage_key: string;
  token: string;
  max_bytes: number;
};

const WORK_CACHE_TTL_MS = 5 * 60 * 1000;

const workDataKeys = {
  all: ["work-data"] as const,
  works: ["work-data", "work"] as const,
  work: (workId: string) => ["work-data", "work", workId] as const,
  version: (versionId: string) => ["work-data", "version", versionId] as const,
  entities: (versionId: string) => ["work-data", "version", versionId, "entities"] as const,
  insights: (versionId: string) => ["work-data", "version", versionId, "insights"] as const,
};

function hasActiveJob(bundle: WorkBundle): boolean {
  return bundle.jobs.some((job) => ["queued", "claimed", "running"].includes(job.lifecycle.current));
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

function bundleContainsVersion(bundle: WorkBundle, versionIds: Set<string>): boolean {
  return bundle.artifacts.some((item) =>
    item.versions.some((version) => versionIds.has(version.id))
    || Boolean(item.latest_version && versionIds.has(item.latest_version.id)),
  );
}

async function discardQuery(queryKey: QueryKey): Promise<void> {
  const queryClient = getQueryClient();
  await queryClient.cancelQueries({ queryKey, exact: true });
  queryClient.removeQueries({ queryKey, exact: true });
}

async function discardVersionData(versionId: string): Promise<void> {
  await Promise.all([
    discardQuery(workDataKeys.entities(versionId)),
    discardQuery(workDataKeys.insights(versionId)),
  ]);
}

async function discardWorkData(workId: string): Promise<void> {
  const queryClient = getQueryClient();
  const bundle = queryClient.getQueryData<WorkBundle>(workDataKeys.work(workId));
  const versionIds = bundle?.artifacts.flatMap((item) => item.versions.map((version) => version.id)) ?? [];

  await Promise.all([
    discardQuery(workDataKeys.work(workId)),
    ...versionIds.map(discardVersionData),
  ]);
}

async function invalidateVersionWorks(versionIds: readonly string[]): Promise<void> {
  const queryClient = getQueryClient();
  const wanted = new Set(versionIds);
  const workIds = new Set<string>();

  for (const [, bundle] of queryClient.getQueriesData<WorkBundle>({ queryKey: workDataKeys.works })) {
    if (bundle && bundleContainsVersion(bundle, wanted)) workIds.add(bundle.work.id);
  }

  await Promise.all([
    ...[...workIds].map(discardWorkData),
    ...versionIds.map(discardVersionData),
  ]);
}

async function mutateVersionWorks<T>(
  versionIds: readonly string[],
  mutation: () => Promise<T>,
): Promise<T> {
  // Cancel/remove before and after the mutation. Query functions consume the
  // TanStack AbortSignal, so a pre-mutation response cannot become the stable
  // post-mutation cache even when requests overlap.
  await invalidateVersionWorks(versionIds);
  const result = await mutation();
  await invalidateVersionWorks(versionIds);
  return result;
}

export function clearWorkDataCache(): void {
  const queryClient = getQueryClient();
  void queryClient.cancelQueries({ queryKey: workDataKeys.all });
  queryClient.removeQueries({ queryKey: workDataKeys.all });
}

export async function createProject(name: string, description?: string): Promise<Project> {
  return apiFetch<Project>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify({ name, description: description ?? "" }),
  });
}

export async function listProjects(): Promise<Project[]> {
  return apiFetch<Project[]>("/api/v1/projects");
}

export async function createWork(projectId: string, title: string, composer?: string): Promise<Work> {
  return apiFetch<Work>(`/api/v1/projects/${projectId}/works`, {
    method: "POST",
    body: JSON.stringify({ title, composer: composer ?? null }),
  });
}

export async function listWorks(projectId: string): Promise<Work[]> {
  return apiFetch<Work[]>(`/api/v1/projects/${projectId}/works`);
}

export async function getWorkBundle(workId: string): Promise<WorkBundle> {
  const queryClient = getQueryClient();
  const queryKey = workDataKeys.work(workId);
  const bundle = await queryClient.fetchQuery({
    queryKey,
    queryFn: ({ signal }) => apiFetch<WorkBundle>(`/api/v1/works/${workId}`, { signal }),
    staleTime: WORK_CACHE_TTL_MS,
  });

  const midiVersionId = currentMidiVersionId(bundle);
  if (hasActiveJob(bundle)) {
    // Processing changes the durable Work over time. Mark the current snapshot
    // stale and discard child evidence so the next existing page poll observes
    // fresh server state without a second cache implementation.
    await queryClient.invalidateQueries({ queryKey, exact: true, refetchType: "none" });
    if (midiVersionId) await discardVersionData(midiVersionId);
  } else if (midiVersionId) {
    await Promise.allSettled([getEntities(midiVersionId), getInsights(midiVersionId)]);
  }

  return bundle;
}

export async function deleteWork(workId: string): Promise<{ deleted: string }> {
  const result = await apiFetch<{ deleted: string }>(`/api/v1/works/${workId}`, {
    method: "DELETE",
  });
  await discardWorkData(workId);
  return result;
}

async function uploadArtifactViaProxy(
  projectId: string,
  file: File,
  workId?: string,
): Promise<{ artifact: Artifact; version: Version }> {
  const token = supabase
    ? (await supabase.auth.getSession()).data.session?.access_token
    : null;

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const formData = new FormData();
  formData.append("file", file);
  if (workId) formData.append("work_id", workId);

  const res = await fetch(`/api/v1/projects/${projectId}/artifacts/upload`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const error =
      typeof body === "object" && body !== null && "error" in body
        ? (body as { error?: unknown }).error
        : undefined;
    throw new Error(typeof error === "string" ? error : `Upload failed: ${res.status}`);
  }

  const result = await res.json() as { artifact: Artifact; version: Version };
  await discardWorkData(result.artifact.work_id);
  return result;
}

export async function uploadArtifact(
  projectId: string,
  file: File,
  workId?: string,
): Promise<{ artifact: Artifact; version: Version }> {
  if (workId) await discardWorkData(workId);
  const directUploadEnabled = process.env.NEXT_PUBLIC_DIRECT_ARTIFACT_UPLOAD !== "false";
  if (!directUploadEnabled || !supabase) {
    return uploadArtifactViaProxy(projectId, file, workId);
  }

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
  await discardWorkData(result.artifact.work_id);
  return result;
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
  return apiFetch<VersionResource>(`/api/v1/versions/${versionId}`);
}

export async function getEntities(versionId: string): Promise<Entity[]> {
  return getQueryClient().fetchQuery({
    queryKey: workDataKeys.entities(versionId),
    queryFn: ({ signal }) => apiFetch<Entity[]>(`/api/v1/versions/${versionId}/entities`, { signal }),
    staleTime: WORK_CACHE_TTL_MS,
  });
}

export async function getInsights(versionId: string): Promise<Insight[]> {
  return getQueryClient().fetchQuery({
    queryKey: workDataKeys.insights(versionId),
    queryFn: ({ signal }) => apiFetch<Insight[]>(`/api/v1/versions/${versionId}/insights`, { signal }),
    staleTime: WORK_CACHE_TTL_MS,
  });
}

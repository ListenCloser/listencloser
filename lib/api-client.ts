import { apiFetch } from "./api";
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

type CacheEntry<T> = {
  value: T;
  expiresAt: number;
};

const WORK_CACHE_TTL_MS = 5 * 60 * 1000;
const workBundleCache = new Map<string, CacheEntry<WorkBundle>>();
const workBundleInflight = new Map<string, Promise<WorkBundle>>();
const entityCache = new Map<string, CacheEntry<Entity[]>>();
const entityInflight = new Map<string, Promise<Entity[]>>();
const insightCache = new Map<string, CacheEntry<Insight[]>>();
const insightInflight = new Map<string, Promise<Insight[]>>();
const versionWorkIndex = new Map<string, string>();
const workCacheGeneration = new Map<string, number>();
const versionCacheGeneration = new Map<string, number>();
let cacheEpoch = 0;

function readCache<T>(cache: Map<string, CacheEntry<T>>, key: string): T | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (entry.expiresAt <= Date.now()) {
    cache.delete(key);
    return null;
  }
  cache.delete(key);
  cache.set(key, entry);
  return entry.value;
}

function writeCache<T>(cache: Map<string, CacheEntry<T>>, key: string, value: T): void {
  cache.set(key, { value, expiresAt: Date.now() + WORK_CACHE_TTL_MS });
}

function generationFor(generations: Map<string, number>, key: string): number {
  return generations.get(key) ?? 0;
}

function bumpGeneration(generations: Map<string, number>, key: string): void {
  generations.set(key, generationFor(generations, key) + 1);
}

function generationIsCurrent(
  epoch: number,
  generations: Map<string, number>,
  key: string,
  generation: number,
): boolean {
  return cacheEpoch === epoch && generationFor(generations, key) === generation;
}

function hasActiveJob(bundle: WorkBundle): boolean {
  return bundle.jobs.some((job) => ["queued", "claimed", "running"].includes(job.lifecycle.current));
}

function indexBundle(workId: string, bundle: WorkBundle): void {
  for (const item of bundle.artifacts) {
    for (const version of item.versions) versionWorkIndex.set(version.id, workId);
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

function invalidateVersionData(versionId: string): void {
  bumpGeneration(versionCacheGeneration, versionId);
  entityCache.delete(versionId);
  entityInflight.delete(versionId);
  insightCache.delete(versionId);
  insightInflight.delete(versionId);
}

function invalidateWorkCache(workId: string): void {
  bumpGeneration(workCacheGeneration, workId);
  workBundleCache.delete(workId);
  workBundleInflight.delete(workId);
  for (const [versionId, indexedWorkId] of versionWorkIndex) {
    if (indexedWorkId !== workId) continue;
    versionWorkIndex.delete(versionId);
    invalidateVersionData(versionId);
  }
}

function invalidateVersionWork(versionId: string): void {
  const workId = versionWorkIndex.get(versionId);
  if (workId) {
    invalidateWorkCache(workId);
    // A version's Work ownership is immutable. Keep the triggering relation so
    // a failed workflow start can be retried without losing the ability to
    // invalidate a source-only Work bundle cached between attempts.
    versionWorkIndex.set(versionId, workId);
    return;
  }
  invalidateVersionData(versionId);
}

function rememberUploadedVersion(result: { artifact: Artifact; version: Version }): { artifact: Artifact; version: Version } {
  // Upload completion is itself a Work mutation. Invalidate any older bundle
  // generation first, then retain the new version→Work relation immediately.
  // This closes the import race where a source-only Work request starts just
  // after upload, workflow creation begins before that request resolves, and
  // workflow invalidation otherwise cannot discover which Work owns the new
  // version. Without this index, the late source-only response can be cached as
  // stable for the full Work TTL even while understanding is running.
  invalidateWorkCache(result.artifact.work_id);
  versionWorkIndex.set(result.version.id, result.artifact.work_id);
  return result;
}

export function clearWorkDataCache(): void {
  cacheEpoch += 1;
  workBundleCache.clear();
  workBundleInflight.clear();
  entityCache.clear();
  entityInflight.clear();
  insightCache.clear();
  insightInflight.clear();
  versionWorkIndex.clear();
  workCacheGeneration.clear();
  versionCacheGeneration.clear();
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
  const cached = readCache(workBundleCache, workId);
  if (cached) return cached;

  const pending = workBundleInflight.get(workId);
  if (pending) return pending;

  const epoch = cacheEpoch;
  const generation = generationFor(workCacheGeneration, workId);
  let request: Promise<WorkBundle>;
  request = apiFetch<WorkBundle>(`/api/v1/works/${workId}`)
    .then(async (bundle) => {
      if (!generationIsCurrent(epoch, workCacheGeneration, workId, generation)) {
        return bundle;
      }

      indexBundle(workId, bundle);
      const midiVersionId = currentMidiVersionId(bundle);
      if (midiVersionId) {
        // A network-fresh Work snapshot is also a child-evidence freshness
        // boundary. During understand jobs, entities/insights can be appended
        // after the MIDI version first appears. Do not let an empty or partial
        // child read survive the next Work poll (or the final terminal read).
        invalidateVersionData(midiVersionId);
      }
      if (!hasActiveJob(bundle)) {
        if (midiVersionId) {
          await Promise.allSettled([getEntities(midiVersionId), getInsights(midiVersionId)]);
        }
        if (generationIsCurrent(epoch, workCacheGeneration, workId, generation)) {
          writeCache(workBundleCache, workId, bundle);
        }
      }
      return bundle;
    })
    .finally(() => {
      if (workBundleInflight.get(workId) === request) {
        workBundleInflight.delete(workId);
      }
    });

  workBundleInflight.set(workId, request);
  return request;
}

export async function deleteWork(workId: string): Promise<{ deleted: string }> {
  const result = await apiFetch<{ deleted: string }>(`/api/v1/works/${workId}`, {
    method: "DELETE",
  });
  invalidateWorkCache(workId);
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

  return rememberUploadedVersion(await res.json());
}

export async function uploadArtifact(
  projectId: string,
  file: File,
  workId?: string,
): Promise<{ artifact: Artifact; version: Version }> {
  if (workId) invalidateWorkCache(workId);
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
  return rememberUploadedVersion(result);
}

export async function startUnderstandWorkflow(
  versionId: string,
  projectId: string,
  transcriptionProfile?: string,
): Promise<{ workflow: Workflow; job: Job }> {
  // Invalidate before the mutation so an already-cached source-only bundle
  // cannot mask workflow creation. Invalidate again after the server commits:
  // selecting the Work can start a fetch while this POST is in flight, and that
  // pre-commit response must not become the stable bundle after creation.
  invalidateVersionWork(versionId);
  const result = await apiFetch<{ workflow: Workflow; job: Job }>("/api/v1/workflows/understand", {
    method: "POST",
    body: JSON.stringify({
      version_id: versionId,
      project_id: projectId,
      ...(transcriptionProfile ? { transcription_profile: transcriptionProfile } : {}),
    }),
  });
  invalidateVersionWork(versionId);
  return result;
}

export async function startVariationWorkflow(
  versionId: string,
  projectId: string,
  transposeSemitones: number,
): Promise<{ workflow: Workflow; job: Job }> {
  invalidateVersionWork(versionId);
  return apiFetch<{ workflow: Workflow; job: Job }>("/api/v1/workflows/variation", {
    method: "POST",
    body: JSON.stringify({
      version_id: versionId,
      project_id: projectId,
      transpose_semitones: transposeSemitones,
    }),
  });
}

export async function startCompareWorkflow(
  versionIdA: string,
  versionIdB: string,
  projectId: string,
): Promise<{ workflow: Workflow; job: Job }> {
  invalidateVersionWork(versionIdA);
  invalidateVersionWork(versionIdB);
  return apiFetch<{ workflow: Workflow; job: Job }>("/api/v1/workflows/compare", {
    method: "POST",
    body: JSON.stringify({
      version_id_a: versionIdA,
      version_id_b: versionIdB,
      project_id: projectId,
    }),
  });
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
  const cached = readCache(entityCache, versionId);
  if (cached) return cached;
  const pending = entityInflight.get(versionId);
  if (pending) return pending;

  const epoch = cacheEpoch;
  const generation = generationFor(versionCacheGeneration, versionId);
  let request: Promise<Entity[]>;
  request = apiFetch<Entity[]>(`/api/v1/versions/${versionId}/entities`)
    .then((entities) => {
      if (generationIsCurrent(epoch, versionCacheGeneration, versionId, generation)) {
        writeCache(entityCache, versionId, entities);
      }
      return entities;
    })
    .finally(() => {
      if (entityInflight.get(versionId) === request) {
        entityInflight.delete(versionId);
      }
    });
  entityInflight.set(versionId, request);
  return request;
}

export async function getInsights(versionId: string): Promise<Insight[]> {
  const cached = readCache(insightCache, versionId);
  if (cached) return cached;
  const pending = insightInflight.get(versionId);
  if (pending) return pending;

  const epoch = cacheEpoch;
  const generation = generationFor(versionCacheGeneration, versionId);
  let request: Promise<Insight[]>;
  request = apiFetch<Insight[]>(`/api/v1/versions/${versionId}/insights`)
    .then((insights) => {
      if (generationIsCurrent(epoch, versionCacheGeneration, versionId, generation)) {
        writeCache(insightCache, versionId, insights);
      }
      return insights;
    })
    .finally(() => {
      if (insightInflight.get(versionId) === request) {
        insightInflight.delete(versionId);
      }
    });
  insightInflight.set(versionId, request);
  return request;
}

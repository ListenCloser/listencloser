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
  return apiFetch<WorkBundle>(`/api/v1/works/${workId}`);
}

export async function uploadArtifact(
  projectId: string,
  file: File,
  workId?: string
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

  return res.json();
}

export async function startUnderstandWorkflow(
  versionId: string,
  projectId: string
): Promise<{ workflow: Workflow; job: Job }> {
  return apiFetch<{ workflow: Workflow; job: Job }>("/api/v1/workflows/understand", {
    method: "POST",
    body: JSON.stringify({ version_id: versionId, project_id: projectId }),
  });
}

export async function startVariationWorkflow(
  versionId: string,
  projectId: string,
  transposeSemitones: number,
): Promise<{ workflow: Workflow; job: Job }> {
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
  return apiFetch<JobStatus>(`/api/v1/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export async function retryJob(jobId: string): Promise<JobStatus> {
  return apiFetch<JobStatus>(`/api/v1/jobs/${jobId}/retry`, {
    method: "POST",
  });
}

export async function getVersionResource(versionId: string): Promise<VersionResource> {
  return apiFetch<VersionResource>(`/api/v1/versions/${versionId}`);
}

export async function getEntities(versionId: string): Promise<Entity[]> {
  return apiFetch<Entity[]>(`/api/v1/versions/${versionId}/entities`);
}

export async function getInsights(versionId: string): Promise<Insight[]> {
  return apiFetch<Insight[]>(`/api/v1/versions/${versionId}/insights`);
}

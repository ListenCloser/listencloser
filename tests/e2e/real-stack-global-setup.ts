/**
 * Global setup for real-stack E2E.
 *
 * Creates a Supabase user, uploads real-piano.m4a via API, triggers the
 * understand workflow, and waits for processing to complete. Saves auth
 * state + work ID to a JSON file for all tests to consume.
 *
 * This eliminates 3-4 redundant browser-based import+processing cycles,
 * saving ~15-20 minutes of CI time.
 */

import { chromium, type FullConfig } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";

const REAL_AUDIO = process.env.REAL_AUDIO_FILE!;
const SUPABASE_URL = process.env.SUPABASE_URL!;
const ANON_KEY = process.env.SUPABASE_ANON_KEY!;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

interface SetupResult {
  accessToken: string;
  refreshToken: string;
  user: Record<string, unknown>;
  projectId: string;
  workId: string;
  versionId: string;
  storageKey: string;
}

async function createTestUser(): Promise<{ accessToken: string; refreshToken: string; user: Record<string, unknown> }> {
  const email = `real-stack-global@real-stack.test`;
  const password = "real-stack-12345678";

  const created = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password, email_confirm: true }),
  });
  const createdBody = await created.json().catch(() => ({}));
  if (!created.ok && createdBody?.code !== "user_already_exists") {
    throw new Error(`failed to create test user: ${created.status} ${JSON.stringify(createdBody)}`);
  }

  const token = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const tokenBody = await token.json();
  if (!tokenBody?.access_token) {
    throw new Error(`failed to sign in test user: ${token.status} ${JSON.stringify(tokenBody)}`);
  }
  return {
    accessToken: tokenBody.access_token,
    refreshToken: tokenBody.refresh_token ?? "",
    user: tokenBody.user,
  };
}

async function apiFetch(path: string, token: string, init?: RequestInit): Promise<Response> {
  return fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
}

async function createProject(token: string): Promise<string> {
  const resp = await apiFetch("/api/v1/projects", token, {
    method: "POST",
    body: JSON.stringify({ name: "E2E Test Project" }),
  });
  if (!resp.ok) throw new Error(`create project failed: ${resp.status} ${await resp.text()}`);
  const data = await resp.json();
  return data.id;
}

async function uploadAndProcess(token: string, projectId: string): Promise<{ workId: string; versionId: string }> {
  // Upload audio
  const audioBytes = readFileSync(REAL_AUDIO);
  const formData = new FormData();
  formData.append("file", new Blob([audioBytes], { type: "audio/m4a" }), "real-piano.m4a");

  const uploadResp = await fetch(`${BACKEND_URL}/api/v1/projects/${projectId}/artifacts/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!uploadResp.ok) throw new Error(`upload failed: ${uploadResp.status} ${await uploadResp.text()}`);
  const uploadData = await uploadResp.json();
  const versionId = uploadData.version_id;

  // Create a work
  const workResp = await apiFetch(`/api/v1/projects/${projectId}/works`, token, {
    method: "POST",
    body: JSON.stringify({ title: "E2E Test Work" }),
  });
  if (!workResp.ok) throw new Error(`create work failed: ${workResp.status} ${await workResp.text()}`);
  const workData = await workResp.json();
  const workId = workData.id;

  // Trigger understand workflow
  const understandResp = await apiFetch("/api/v1/workflows/understand", token, {
    method: "POST",
    body: JSON.stringify({
      work_id: workId,
      input_version_ids: [versionId],
    }),
  });
  if (!understandResp.ok) throw new Error(`understand failed: ${understandResp.status} ${await understandResp.text()}`);
  const understandData = await understandResp.json();
  const jobId = understandData.job_id;

  // Poll job until completion
  console.log(`[global-setup] waiting for job ${jobId} to complete...`);
  const startTime = Date.now();
  while (Date.now() - startTime < 300_000) {
    const jobResp = await apiFetch(`/api/v1/jobs/${jobId}`, token);
    if (!jobResp.ok) throw new Error(`job status failed: ${jobResp.status}`);
    const jobData = await jobResp.json();
    const stage = jobData.stage;
    const progress = jobData.progress ?? 0;
    const message = jobData.status_message ?? "";

    if (stage === "succeeded") {
      console.log(`[global-setup] job succeeded in ${((Date.now() - startTime) / 1000).toFixed(1)}s`);
      return { workId, versionId };
    }
    if (stage === "failed") {
      throw new Error(`job failed: ${jobData.error_message} ${JSON.stringify(jobData.error_details)}`);
    }

    console.log(`[global-setup] job ${stage} ${(progress * 100).toFixed(0)}% ${message}`);
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("job timed out after 300s");
}

export default async function globalSetup(config: FullConfig) {
  if (!REAL_AUDIO || !SUPABASE_URL || !ANON_KEY || !SERVICE_KEY) {
    console.log("[global-setup] skipping — env not configured");
    return;
  }

  console.log("[global-setup] creating test user...");
  const { accessToken, refreshToken, user } = await createTestUser();

  console.log("[global-setup] creating project...");
  const projectId = await createProject(accessToken);

  console.log("[global-setup] uploading and processing audio...");
  const { workId, versionId } = await uploadAndProcess(accessToken, projectId);

  const sk = `sb-${new URL(SUPABASE_URL).hostname.split(".")[0]}-auth-token`;
  const result: SetupResult = {
    accessToken,
    refreshToken,
    user,
    projectId,
    workId,
    versionId,
    storageKey: sk,
  };

  const outPath = "/tmp/real-stack-setup.json";
  writeFileSync(outPath, JSON.stringify(result, null, 2));
  console.log(`[global-setup] done. workId=${workId} saved to ${outPath}`);
}

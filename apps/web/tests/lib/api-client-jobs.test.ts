import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, post, del, apiFetch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  del: vi.fn(),
  apiFetch: vi.fn(),
}));

vi.mock("@/lib/openapi-client", () => ({
  openapiClient: { GET: get, POST: post, DELETE: del },
  requireOpenApiData: <T,>({ data, error, response }: { data?: T; error?: unknown; response: Response }): T => {
    if (data !== undefined) return data;
    const message =
      typeof error === "object" && error !== null && "error" in error
        ? (error as { error?: unknown }).error
        : undefined;
    throw new Error(typeof message === "string" ? message : `Request failed: ${response.status}`);
  },
}));
vi.mock("@/lib/api", () => ({ apiFetch }));
vi.mock("@/lib/supabase", () => ({ supabase: null }));

import { cancelJob, deleteWork, getJob, retryJob } from "@/lib/api-client";
import { getQueryClient } from "@/lib/query-client";
import type { JobStatus } from "@/lib/domain.types";

const job: JobStatus = {
  id: "job-1",
  workflow_id: "workflow-1",
  capability: "understand",
  stage: "running",
  progress: 0.5,
  message: "Processing",
  error: null,
  input_version_ids: ["version-1"],
  output_version_ids: [],
};

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

describe("generated job and Work-delete transport", () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
    del.mockReset();
    apiFetch.mockReset();
    getQueryClient().clear();
  });

  it("reads job state through the generated path operation", async () => {
    get.mockResolvedValueOnce(ok(job));
    await expect(getJob("job-1")).resolves.toEqual(job);
    expect(get).toHaveBeenCalledWith("/api/v1/jobs/{job_id}", {
      params: { path: { job_id: "job-1" } },
    });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("cancels and retries through generated operations while preserving cache invalidation", async () => {
    post.mockResolvedValueOnce(ok({ ...job, stage: "cancelled" }));
    await expect(cancelJob("job-1")).resolves.toMatchObject({ stage: "cancelled" });
    expect(post).toHaveBeenNthCalledWith(1, "/api/v1/jobs/{job_id}/cancel", {
      params: { path: { job_id: "job-1" } },
    });
    expect(getQueryClient().getQueryData(["work-data-meta", "epoch"])).toBe(1);

    post.mockResolvedValueOnce(ok({ ...job, stage: "queued" }));
    await expect(retryJob("job-1")).resolves.toMatchObject({ stage: "queued" });
    expect(post).toHaveBeenNthCalledWith(2, "/api/v1/jobs/{job_id}/retry", {
      params: { path: { job_id: "job-1" } },
    });
    expect(getQueryClient().getQueryData(["work-data-meta", "epoch"])).toBe(2);
  });

  it("deletes a Work through the generated operation", async () => {
    del.mockResolvedValueOnce(ok({ deleted: "work-1" }));
    await expect(deleteWork("work-1")).resolves.toEqual({ deleted: "work-1" });
    expect(del).toHaveBeenCalledWith("/api/v1/works/{work_id}", {
      params: { path: { work_id: "work-1" } },
    });
    expect(apiFetch).not.toHaveBeenCalled();
  });
});

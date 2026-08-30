import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  GET: vi.fn(),
  POST: vi.fn(),
  apiFetch: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiClient: { GET: mocks.GET, POST: mocks.POST },
  apiFetch: mocks.apiFetch,
  apiResponseError: (body: unknown, status: number) => {
    const error = typeof body === "object" && body !== null && "error" in body
      ? (body as { error?: unknown }).error
      : undefined;
    return new Error(typeof error === "string" ? error : `Request failed: ${status}`);
  },
}));

vi.mock("@/lib/supabase", () => ({ supabase: null }));

import { createProject, createWork, listProjects, listWorks } from "@/lib/api-client";

const project = {
  id: "project-1",
  owner_id: "user-1",
  name: "Library",
  description: "Music workspace",
  archived_at: null,
  created_at: "2026-08-30T00:00:00Z",
  updated_at: "2026-08-30T00:00:00Z",
};

const work = {
  id: "work-1",
  project_id: "project-1",
  title: "Study",
  composer: null,
  created_at: "2026-08-30T00:00:00Z",
  updated_at: "2026-08-30T00:00:00Z",
};

function ok<T>(data: T) {
  return {
    data,
    error: undefined,
    response: new Response(JSON.stringify(data), { status: 200 }),
  };
}

describe("generated project/work transport", () => {
  beforeEach(() => {
    mocks.GET.mockReset();
    mocks.POST.mockReset();
    mocks.apiFetch.mockReset();
  });

  it("uses generated request bodies for project creation", async () => {
    mocks.POST.mockResolvedValueOnce(ok(project));

    await expect(createProject("Library", "Music workspace")).resolves.toEqual(project);
    expect(mocks.POST).toHaveBeenCalledWith("/api/v1/projects", {
      body: { name: "Library", description: "Music workspace" },
    });
    expect(mocks.apiFetch).not.toHaveBeenCalled();
  });

  it("uses generated path parameters and request bodies for Work calls", async () => {
    mocks.POST.mockResolvedValueOnce(ok(work));
    mocks.GET.mockResolvedValueOnce(ok([work]));

    await expect(createWork("project-1", "Study")).resolves.toEqual(work);
    await expect(listWorks("project-1")).resolves.toEqual([work]);

    expect(mocks.POST).toHaveBeenCalledWith("/api/v1/projects/{project_id}/works", {
      params: { path: { project_id: "project-1" } },
      body: { title: "Study", composer: null },
    });
    expect(mocks.GET).toHaveBeenCalledWith("/api/v1/projects/{project_id}/works", {
      params: { path: { project_id: "project-1" } },
    });
  });

  it("keeps persisted Project/Work invariants explicit at the application boundary", async () => {
    mocks.GET
      .mockResolvedValueOnce(ok([{ ...project, id: undefined }]))
      .mockResolvedValueOnce(ok([{ ...work, composer: undefined }]));

    await expect(listProjects()).rejects.toThrow("Invalid Project response");
    await expect(listWorks("project-1")).rejects.toThrow("Invalid Work response");
  });

  it("preserves structured transport errors", async () => {
    mocks.GET.mockResolvedValueOnce({
      data: undefined,
      error: { error: "forbidden" },
      response: new Response(null, { status: 403 }),
    });

    await expect(listProjects()).rejects.toThrow("forbidden");
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/lib/openapi-client", () => ({
  openapiClient: { GET: get, POST: post },
  requireOpenApiData: <T,>({ data, error, response }: { data?: T; error?: unknown; response: Response }): T => {
    if (data !== undefined) return data;
    const message =
      typeof error === "object" && error !== null && "error" in error
        ? (error as { error?: unknown }).error
        : undefined;
    throw new Error(typeof message === "string" ? message : `Request failed: ${response.status}`);
  },
}));

import { createProject, createWork, listProjects, listWorks } from "@/lib/api-client";

const project = {
  id: "00000000-0000-0000-0000-000000000001",
  owner_id: "user-1",
  name: "Library",
  description: "Music workspace",
  created_at: "2026-08-30T00:00:00Z",
  updated_at: "2026-08-30T00:00:00Z",
  archived_at: null,
};

const work = {
  id: "00000000-0000-0000-0000-000000000002",
  project_id: project.id,
  title: "Test Work",
  composer: null,
  created_at: "2026-08-30T00:00:00Z",
  updated_at: "2026-08-30T00:00:00Z",
};

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

describe("generated project/work API transport", () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
  });

  it("creates and lists Projects through generated operations", async () => {
    post.mockResolvedValueOnce(ok(project));
    get.mockResolvedValueOnce(ok([project]));

    await expect(createProject("Library", "Music workspace")).resolves.toEqual(project);
    await expect(listProjects()).resolves.toEqual([project]);

    expect(post).toHaveBeenCalledWith("/api/v1/projects", {
      body: { name: "Library", description: "Music workspace" },
    });
    expect(get).toHaveBeenCalledWith("/api/v1/projects");
  });

  it("creates and lists Works through generated path parameters", async () => {
    post.mockResolvedValueOnce(ok(work));
    get.mockResolvedValueOnce(ok([work]));

    await expect(createWork(project.id, "Test Work")).resolves.toEqual(work);
    await expect(listWorks(project.id)).resolves.toEqual([work]);

    expect(post).toHaveBeenCalledWith("/api/v1/projects/{project_id}/works", {
      params: { path: { project_id: project.id } },
      body: { title: "Test Work", composer: null },
    });
    expect(get).toHaveBeenCalledWith("/api/v1/projects/{project_id}/works", {
      params: { path: { project_id: project.id } },
    });
  });

  it("fails closed when a persisted Project omits a server-materialized field", async () => {
    const { id: _id, ...invalidProject } = project;
    get.mockResolvedValueOnce(ok([invalidProject]));

    await expect(listProjects()).rejects.toThrow('Invalid Project response: missing server field "id"');
  });

  it("fails closed when a persisted Work omits a server-materialized field", async () => {
    const { composer: _composer, ...invalidWork } = work;
    get.mockResolvedValueOnce(ok([invalidWork]));

    await expect(listWorks(project.id)).rejects.toThrow('Invalid Work response: missing server field "composer"');
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkBundle } from "@/lib/domain.types";

const { get, post, mockUploadToSignedUrl } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  mockUploadToSignedUrl: vi.fn(),
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
vi.mock("@/lib/supabase", () => ({
  supabase: {
    storage: {
      from: vi.fn(() => ({ uploadToSignedUrl: mockUploadToSignedUrl })),
    },
  },
}));

import {
  clearWorkDataCache,
  getWorkBundle,
  startUnderstandWorkflow,
  uploadArtifact,
} from "@/lib/api-client";

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

function sourceBundle(title: string): WorkBundle {
  const version = {
    id: "source-1",
    artifact_id: "artifact-source",
    parent_version_id: null,
    lineage: [],
    storage_key: "source.wav",
    storage_bucket: "artifacts",
    byte_size: 1,
    sha256: null,
    created_at: "2026-08-28T00:00:00Z",
    created_by: null,
    produced_by_job_id: null,
    label: "Original",
    metadata: {},
  };
  return {
    work: {
      id: "work-1",
      project_id: "project-1",
      title,
      composer: null,
      created_at: "2026-08-28T00:00:00Z",
      updated_at: "2026-08-28T00:00:00Z",
    },
    artifacts: [{
      artifact: {
        id: "artifact-source",
        work_id: "work-1",
        kind: "audio_original",
        mime_type: "audio/wav",
        created_at: "2026-08-28T00:00:00Z",
      },
      versions: [version],
      latest_version: version,
      signed_url: "https://example.test/source.wav",
    }],
    jobs: [],
  };
}

function workflowJob() {
  return {
    workflow: {
      id: "workflow-1",
      project_id: "project-1",
      kind: "understand" as const,
      target_version_id: "source-1",
      parameters: {},
      created_at: "2026-08-28T00:00:00Z",
    },
    job: {
      id: "job-1",
      workflow_id: "workflow-1",
      capability: {
        name: "understand",
        version: "1",
        accepted_input_kinds: [],
        produces_output_kinds: [],
        parameters: {},
        failure_modes: [],
      },
      lifecycle: {
        current: "queued" as const,
        progress: 0,
        message: "",
        stages: [],
        retry_count: 0,
        max_retries: 3,
        lease_expires_at: null,
        started_at: null,
        completed_at: null,
      },
      input_version_ids: ["source-1"],
      output_version_ids: [],
      parameters: {},
      cache_key: null,
      error: null,
      error_details: {},
      provenance: {},
      created_at: "2026-08-28T00:00:00Z",
      created_by: null,
    },
  };
}

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

function installUploadResult() {
  const uploadResult = {
    artifact: {
      id: "artifact-source",
      work_id: "work-1",
      kind: "audio_original" as const,
      mime_type: "audio/wav",
      created_at: "2026-08-28T00:00:00Z",
    },
    version: sourceBundle("uploaded").artifacts[0].latest_version!,
  };
  mockUploadToSignedUrl.mockResolvedValue({ error: null });
  post.mockImplementation(async (path) => {
    if (path === "/api/v1/projects/{project_id}/artifacts/upload-intent") {
      return ok({
        bucket: "artifacts",
        storage_key: "work-1/source.wav",
        token: "signed-token",
        max_bytes: 10_000,
      });
    }
    if (path === "/api/v1/projects/{project_id}/artifacts/finalize-upload") {
      return ok(uploadResult);
    }
    throw new Error(`Unexpected generated upload API call: ${path}`);
  });
  return uploadResult;
}

describe("fresh upload Work invalidation", () => {
  beforeEach(() => {
    clearWorkDataCache();
    get.mockReset();
    post.mockReset();
    mockUploadToSignedUrl.mockReset();
  });

  it("uses generated JSON bookends while keeping the binary upload in signed Supabase Storage", async () => {
    const uploadResult = installUploadResult();
    const file = new File(["audio"], "source.wav", { type: "audio/wav" });

    await expect(uploadArtifact("project-1", file, "work-1")).resolves.toEqual(uploadResult);

    expect(post).toHaveBeenNthCalledWith(1, "/api/v1/projects/{project_id}/artifacts/upload-intent", {
      params: { path: { project_id: "project-1" } },
      body: {
        filename: "source.wav",
        byte_size: file.size,
        content_type: "audio/wav",
        work_id: "work-1",
      },
    });
    expect(mockUploadToSignedUrl).toHaveBeenCalledWith(
      "work-1/source.wav",
      "signed-token",
      file,
    );
    expect(post).toHaveBeenNthCalledWith(2, "/api/v1/projects/{project_id}/artifacts/finalize-upload", {
      params: { path: { project_id: "project-1" } },
      body: {
        filename: "source.wav",
        byte_size: file.size,
        content_type: "audio/wav",
        work_id: "work-1",
        storage_key: "work-1/source.wav",
      },
    });
    expect(get).not.toHaveBeenCalled();
  });

  it("workflow start does not join or cache a source-only Work request that began after upload", async () => {
    installUploadResult();
    await uploadArtifact("project-1", new File(["audio"], "source.wav", { type: "audio/wav" }));

    const stale = deferred<WorkBundle>();
    let workFetches = 0;
    get.mockImplementation(async (path) => {
      if (path === "/api/v1/works/{work_id}") {
        workFetches += 1;
        return ok(workFetches === 1 ? await stale.promise : sourceBundle("Fresh source"));
      }
      throw new Error(`Unexpected generated GET: ${path}`);
    });
    post.mockImplementation(async (path) => {
      if (path === "/api/v1/workflows/understand") return ok(workflowJob());
      throw new Error(`Unexpected generated POST: ${path}`);
    });

    const staleOpen = getWorkBundle("work-1");
    expect(workFetches).toBe(1);

    await startUnderstandWorkflow("source-1", "project-1", "auto");
    const freshOpen = getWorkBundle("work-1");

    // This is the regression: without the upload-time version→Work index,
    // workflow invalidation misses the Work and this call joins staleOpen.
    expect(workFetches).toBe(2);
    const fresh = await freshOpen;
    expect(fresh.work.title).toBe("Fresh source");

    stale.resolve(sourceBundle("Stale source"));
    await staleOpen;

    const revisited = await getWorkBundle("work-1");
    expect(revisited.work.title).toBe("Fresh source");
    expect(workFetches).toBe(2);
  });

  it("invalidates a source-only Work fetch that starts while workflow creation is in flight", async () => {
    installUploadResult();
    await uploadArtifact("project-1", new File(["audio"], "source.wav", { type: "audio/wav" }));

    const workflow = deferred<ReturnType<typeof workflowJob>>();
    const stale = deferred<WorkBundle>();
    let workFetches = 0;
    post.mockImplementation(async (path) => {
      if (path === "/api/v1/workflows/understand") return ok(await workflow.promise);
      throw new Error(`Unexpected generated POST: ${path}`);
    });
    get.mockImplementation(async (path) => {
      if (path === "/api/v1/works/{work_id}") {
        workFetches += 1;
        return ok(workFetches === 1 ? await stale.promise : sourceBundle("After workflow commit"));
      }
      throw new Error(`Unexpected generated GET: ${path}`);
    });

    // Workflow creation has invalidated the previous generation, but the server
    // has not committed the workflow yet. Selecting the newly uploaded Work can
    // therefore legitimately start a source-only read in this window.
    const workflowStart = startUnderstandWorkflow("source-1", "project-1", "auto");
    const duringMutation = getWorkBundle("work-1");
    expect(workFetches).toBe(1);

    workflow.resolve(workflowJob());
    await workflowStart;

    // Successful commit must invalidate the read that began during the POST, so
    // the caller observes the active workflow instead of joining stale data.
    const afterCommit = getWorkBundle("work-1");
    expect(workFetches).toBe(2);
    expect((await afterCommit).work.title).toBe("After workflow commit");

    stale.resolve(sourceBundle("Before workflow commit"));
    await duringMutation;
    expect((await getWorkBundle("work-1")).work.title).toBe("After workflow commit");
    expect(workFetches).toBe(2);
  });

  it("preserves upload ownership when workflow start fails so a retry invalidates an in-flight source bundle", async () => {
    installUploadResult();
    await uploadArtifact("project-1", new File(["audio"], "source.wav", { type: "audio/wav" }));

    const stale = deferred<WorkBundle>();
    let workFetches = 0;
    let workflowStarts = 0;
    get.mockImplementation(async (path) => {
      if (path === "/api/v1/works/{work_id}") {
        workFetches += 1;
        return ok(workFetches === 1 ? await stale.promise : sourceBundle("Fresh after retry"));
      }
      throw new Error(`Unexpected generated GET: ${path}`);
    });
    post.mockImplementation(async (path) => {
      if (path === "/api/v1/workflows/understand") {
        workflowStarts += 1;
        if (workflowStarts === 1) throw new Error("workflow unavailable");
        return ok(workflowJob());
      }
      throw new Error(`Unexpected generated POST: ${path}`);
    });

    await expect(startUnderstandWorkflow("source-1", "project-1", "auto")).rejects.toThrow("workflow unavailable");

    // A source-only refresh may begin while the user is looking at the saved
    // recording after the failed start. It has not resolved yet, so it cannot
    // restore version ownership by indexing the bundle itself.
    const staleOpen = getWorkBundle("work-1");
    expect(workFetches).toBe(1);

    await startUnderstandWorkflow("source-1", "project-1", "auto");
    const freshOpen = getWorkBundle("work-1");

    // The retry must still know which Work owns source-1, invalidate staleOpen,
    // and issue a fresh bundle request rather than joining the source-only one.
    expect(workFetches).toBe(2);
    expect((await freshOpen).work.title).toBe("Fresh after retry");

    stale.resolve(sourceBundle("Stale after failure"));
    await staleOpen;
    expect((await getWorkBundle("work-1")).work.title).toBe("Fresh after retry");
    expect(workFetches).toBe(2);
  });
});

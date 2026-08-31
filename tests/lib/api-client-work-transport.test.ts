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
vi.mock("@/lib/supabase", () => ({ supabase: null }));

import {
  clearWorkDataCache,
  getWorkBundle,
  startCompareWorkflow,
  startUnderstandWorkflow,
  startVariationWorkflow,
} from "@/lib/api-client";
import { getQueryClient } from "@/lib/query-client";

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

function completeJob() {
  return {
    id: "job-1",
    workflow_id: "workflow-1",
    capability: {
      name: "understand",
      version: "1",
      accepted_input_kinds: ["audio_original"] as const,
      produces_output_kinds: ["midi_performance"] as const,
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
    input_version_ids: ["version-1"],
    output_version_ids: [],
    parameters: {},
    cache_key: null,
    error: null,
    error_details: {},
    provenance: {},
    created_at: "2026-08-30T00:00:00Z",
    created_by: null,
  };
}

function completeWorkflow() {
  return {
    id: "workflow-1",
    project_id: "project-1",
    kind: "understand" as const,
    target_version_id: "version-1",
    parameters: {},
    created_at: "2026-08-30T00:00:00Z",
  };
}

function workflowJob() {
  return { workflow: completeWorkflow(), job: completeJob() };
}

function workBundle() {
  const version = {
    id: "version-1",
    artifact_id: "artifact-1",
    parent_version_id: null,
    lineage: [],
    storage_key: "source.wav",
    storage_bucket: "artifacts",
    byte_size: 4,
    sha256: null,
    created_at: "2026-08-30T00:00:00Z",
    created_by: null,
    produced_by_job_id: null,
    label: "Original",
    metadata: {},
  };
  return {
    work: {
      id: "work-1",
      project_id: "project-1",
      title: "Transport fixture",
      composer: null,
      created_at: "2026-08-30T00:00:00Z",
      updated_at: "2026-08-30T00:00:00Z",
    },
    artifacts: [{
      artifact: {
        id: "artifact-1",
        work_id: "work-1",
        kind: "audio_original" as const,
        mime_type: "audio/wav",
        created_at: "2026-08-30T00:00:00Z",
      },
      versions: [version],
      latest_version: version,
      signed_url: "https://example.test/source.wav",
    }],
    jobs: [completeJob()],
  };
}

describe("final generated Work/workflow transport", () => {
  beforeEach(() => {
    getQueryClient().clear();
    clearWorkDataCache();
    get.mockReset();
    post.mockReset();
  });

  it("loads the persisted Work graph through the generated path operation", async () => {
    const bundle = workBundle();
    get.mockResolvedValueOnce(ok(bundle));

    await expect(getWorkBundle("work-1")).resolves.toEqual(bundle);
    expect(get).toHaveBeenCalledWith("/api/v1/works/{work_id}", {
      params: { path: { work_id: "work-1" } },
    });
  });

  it("fails closed when a Work artifact bundle omits a materialized default", async () => {
    const bundle = workBundle();
    const { signed_url: _signedUrl, ...invalidArtifactBundle } = bundle.artifacts[0];
    get.mockResolvedValueOnce(ok({ ...bundle, artifacts: [invalidArtifactBundle] }));

    await expect(getWorkBundle("work-1")).rejects.toThrow(
      'Invalid WorkArtifactBundle response: missing server field "signed_url"',
    );
  });

  it("fails closed when a nested Job lifecycle omits a materialized default", async () => {
    const bundle = workBundle();
    const { stages: _stages, ...invalidLifecycle } = bundle.jobs[0].lifecycle;
    get.mockResolvedValueOnce(ok({
      ...bundle,
      jobs: [{ ...bundle.jobs[0], lifecycle: invalidLifecycle }],
    }));

    await expect(getWorkBundle("work-1")).rejects.toThrow(
      'Invalid JobLifecycle response: missing server field "stages"',
    );
  });

  it("starts understand, variation, and compare through generated operations", async () => {
    post.mockResolvedValue(ok(workflowJob()));

    await startUnderstandWorkflow("version-1", "project-1", "solo_piano");
    await startVariationWorkflow("version-1", "project-1", 2);
    await startCompareWorkflow("version-1", "version-2", "project-1");

    expect(post).toHaveBeenNthCalledWith(1, "/api/v1/workflows/understand", {
      body: {
        version_id: "version-1",
        project_id: "project-1",
        transcription_profile: "solo_piano",
      },
    });
    expect(post).toHaveBeenNthCalledWith(2, "/api/v1/workflows/variation", {
      body: {
        version_id: "version-1",
        project_id: "project-1",
        transpose_semitones: 2,
      },
    });
    expect(post).toHaveBeenNthCalledWith(3, "/api/v1/workflows/compare", {
      body: {
        version_id_a: "version-1",
        version_id_b: "version-2",
        project_id: "project-1",
      },
    });
  });

  it("fails closed when a workflow response omits a persisted default", async () => {
    const result = workflowJob();
    const { parameters: _parameters, ...invalidWorkflow } = result.workflow;
    post.mockResolvedValueOnce(ok({ ...result, workflow: invalidWorkflow }));

    await expect(startUnderstandWorkflow("version-1", "project-1", "auto")).rejects.toThrow(
      'Invalid Workflow response: missing server field "parameters"',
    );
  });
});

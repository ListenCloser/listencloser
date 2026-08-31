import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkBundle } from "@/lib/domain.types";

const { get } = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/openapi-client", () => ({
  openapiClient: { GET: get },
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

import { apiFetch } from "@/lib/api";
import { clearWorkDataCache, getEntities, getInsights, getWorkBundle } from "@/lib/api-client";
import { getQueryClient } from "@/lib/query-client";

const mockApiFetch = vi.mocked(apiFetch);

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

function terminalBundle(): WorkBundle {
  const version = {
    id: "midi-1",
    artifact_id: "artifact-midi",
    parent_version_id: null,
    lineage: [],
    storage_key: "midi-1.mid",
    storage_bucket: "artifacts",
    byte_size: 1,
    sha256: null,
    created_at: "2026-08-30T00:00:00Z",
    created_by: null,
    produced_by_job_id: null,
    label: "Transcription",
    metadata: {},
  };
  return {
    work: {
      id: "work-1",
      project_id: "project-1",
      title: "Critical-path fixture",
      composer: null,
      created_at: "2026-08-30T00:00:00Z",
      updated_at: "2026-08-30T00:00:00Z",
    },
    artifacts: [{
      artifact: {
        id: "artifact-midi",
        work_id: "work-1",
        kind: "midi_performance",
        mime_type: "audio/midi",
        created_at: "2026-08-30T00:00:00Z",
      },
      versions: [version],
      latest_version: version,
      signed_url: "https://example.test/midi-1.mid",
    }],
    jobs: [],
  };
}

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

describe("saved Work open critical path", () => {
  beforeEach(() => {
    getQueryClient().clear();
    clearWorkDataCache();
    mockApiFetch.mockReset();
    get.mockReset();
  });

  it("returns the durable bundle while entity and insight warmers are still unresolved", async () => {
    const entities = deferred<never[]>();
    const insights = deferred<never[]>();
    mockApiFetch.mockImplementation(async (url) => {
      if (url === "/api/v1/works/work-1") return terminalBundle();
      throw new Error(`Unexpected API call: ${url}`);
    });
    get.mockImplementation(async (path) => {
      if (path === "/api/v1/versions/{version_id}/entities") return ok(await entities.promise);
      if (path === "/api/v1/versions/{version_id}/insights") return ok(await insights.promise);
      throw new Error(`Unexpected generated GET: ${path}`);
    });

    let openSettled = false;
    const opening = getWorkBundle("work-1").then((bundle) => {
      openSettled = true;
      return bundle;
    });

    await vi.waitFor(() => {
      expect(get).toHaveBeenCalledWith("/api/v1/versions/{version_id}/entities", {
        params: { path: { version_id: "midi-1" } },
      });
      expect(get).toHaveBeenCalledWith("/api/v1/versions/{version_id}/insights", {
        params: { path: { version_id: "midi-1" } },
      });
    });
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    expect(openSettled).toBe(true);
    expect((await opening).work.id).toBe("work-1");

    const foregroundEntities = getEntities("midi-1");
    const foregroundInsights = getInsights("midi-1");
    expect(get.mock.calls.filter(([path]) => path === "/api/v1/versions/{version_id}/entities")).toHaveLength(1);
    expect(get.mock.calls.filter(([path]) => path === "/api/v1/versions/{version_id}/insights")).toHaveLength(1);

    entities.resolve([]);
    insights.resolve([]);
    await Promise.all([foregroundEntities, foregroundInsights]);
  });
});

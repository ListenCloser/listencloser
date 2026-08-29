import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Entity, WorkBundle } from "@/lib/domain.types";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/supabase", () => ({ supabase: null }));

import { apiFetch } from "@/lib/api";
import {
  clearWorkDataCache,
  getEntities,
  getWorkBundle,
  startUnderstandWorkflow,
} from "@/lib/api-client";

const mockApiFetch = vi.mocked(apiFetch);

function savedBundle(title = "Piece"): WorkBundle {
  return {
    work: {
      id: "work-1",
      project_id: "project-1",
      title,
      composer: null,
      created_at: "2026-08-28T00:00:00Z",
      updated_at: "2026-08-28T00:00:00Z",
    },
    artifacts: [
      {
        artifact: {
          id: "artifact-midi",
          work_id: "work-1",
          kind: "midi_performance",
          mime_type: "audio/midi",
          created_at: "2026-08-28T00:00:00Z",
        },
        versions: [
          {
            id: "midi-1",
            artifact_id: "artifact-midi",
            parent_version_id: null,
            lineage: [],
            storage_key: "midi.mid",
            storage_bucket: "artifacts",
            byte_size: 1,
            sha256: null,
            created_at: "2026-08-28T00:00:00Z",
            created_by: null,
            produced_by_job_id: null,
            label: "Transcription",
            metadata: {},
          },
        ],
        latest_version: {
          id: "midi-1",
          artifact_id: "artifact-midi",
          parent_version_id: null,
          lineage: [],
          storage_key: "midi.mid",
          storage_bucket: "artifacts",
          byte_size: 1,
          sha256: null,
          created_at: "2026-08-28T00:00:00Z",
          created_by: null,
          produced_by_job_id: null,
          label: "Transcription",
          metadata: {},
        },
        signed_url: "https://example.test/midi.mid",
      },
    ],
    jobs: [],
  };
}

function entity(id: string): Entity {
  return {
    id,
    version_id: "midi-1",
    kind: "note",
    span: {
      start_seconds: 0,
      end_seconds: 1,
      start_beat: null,
      end_beat: null,
      start_measure: null,
      end_measure: null,
    },
    note: {
      pitch: 60,
      start_seconds: 0,
      end_seconds: 1,
      velocity: 80,
      voice: 1,
    },
    chord: null,
    cadence: null,
    label: id,
  };
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

function installResponses() {
  mockApiFetch.mockImplementation(async (url, options) => {
    if (url === "/api/v1/works/work-1") return savedBundle();
    if (url === "/api/v1/versions/midi-1/entities") return [];
    if (url === "/api/v1/versions/midi-1/insights") return [];
    if (url === "/api/v1/workflows/understand" && options?.method === "POST") {
      return { workflow: {}, job: {} };
    }
    throw new Error(`Unexpected API call: ${url}`);
  });
}

describe("saved work hydration cache", () => {
  beforeEach(() => {
    clearWorkDataCache();
    mockApiFetch.mockReset();
    installResponses();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("warms notes and insights once and reuses the full saved work on revisit", async () => {
    const first = await getWorkBundle("work-1");
    const second = await getWorkBundle("work-1");

    expect(second).toBe(first);
    expect(mockApiFetch).toHaveBeenCalledTimes(3);
    expect(mockApiFetch).toHaveBeenCalledWith("/api/v1/works/work-1");
    expect(mockApiFetch).toHaveBeenCalledWith("/api/v1/versions/midi-1/entities");
    expect(mockApiFetch).toHaveBeenCalledWith("/api/v1/versions/midi-1/insights");
  });

  it("deduplicates simultaneous opens of the same work", async () => {
    await Promise.all([getWorkBundle("work-1"), getWorkBundle("work-1")]);

    expect(mockApiFetch.mock.calls.filter(([url]) => url === "/api/v1/works/work-1")).toHaveLength(1);
  });

  it("invalidates a cached work when processing starts from one of its versions", async () => {
    await getWorkBundle("work-1");
    await startUnderstandWorkflow("midi-1", "project-1", "auto");
    await getWorkBundle("work-1");

    expect(mockApiFetch.mock.calls.filter(([url]) => url === "/api/v1/works/work-1")).toHaveLength(2);
  });

  it("does not let an invalidated in-flight work open overwrite a newer cache", async () => {
    const initialNow = 1_000_000;
    const now = vi.spyOn(Date, "now").mockReturnValue(initialNow);
    await getWorkBundle("work-1");

    // Expire only the bundle TTL. The version→work index intentionally remains
    // available so the workflow mutation can invalidate the in-flight reopen.
    now.mockReturnValue(initialNow + 5 * 60 * 1000 + 1);

    const staleBundle = deferred<WorkBundle>();
    const freshBundle = savedBundle("Fresh piece");
    let workFetches = 0;
    mockApiFetch.mockImplementation(async (url, options) => {
      if (url === "/api/v1/works/work-1") {
        workFetches += 1;
        if (workFetches === 1) return staleBundle.promise;
        return freshBundle;
      }
      if (url === "/api/v1/versions/midi-1/entities") return [];
      if (url === "/api/v1/versions/midi-1/insights") return [];
      if (url === "/api/v1/workflows/understand" && options?.method === "POST") {
        return { workflow: {}, job: {} };
      }
      throw new Error(`Unexpected API call: ${url}`);
    });

    const staleOpen = getWorkBundle("work-1");
    expect(workFetches).toBe(1);

    await startUnderstandWorkflow("midi-1", "project-1", "auto");
    const freshOpen = getWorkBundle("work-1");
    expect(workFetches).toBe(2);
    const fresh = await freshOpen;
    expect(fresh.work.title).toBe("Fresh piece");

    staleBundle.resolve(savedBundle("Stale piece"));
    await staleOpen;

    const revisited = await getWorkBundle("work-1");
    expect(revisited).toBe(fresh);
    expect(revisited.work.title).toBe("Fresh piece");
    expect(workFetches).toBe(2);
  });

  it("starts a fresh entity read after invalidating an older in-flight request", async () => {
    const staleEntities = deferred<Entity[]>();
    const freshEntities = deferred<Entity[]>();
    let entityFetches = 0;

    mockApiFetch.mockImplementation(async (url, options) => {
      if (url === "/api/v1/versions/midi-1/entities") {
        entityFetches += 1;
        return entityFetches === 1 ? staleEntities.promise : freshEntities.promise;
      }
      if (url === "/api/v1/workflows/understand" && options?.method === "POST") {
        return { workflow: {}, job: {} };
      }
      throw new Error(`Unexpected API call: ${url}`);
    });

    const staleRequest = getEntities("midi-1");
    expect(entityFetches).toBe(1);

    await startUnderstandWorkflow("midi-1", "project-1", "auto");
    const freshRequest = getEntities("midi-1");
    expect(entityFetches).toBe(2);

    const fresh = [entity("fresh")];
    freshEntities.resolve(fresh);
    expect(await freshRequest).toEqual(fresh);

    staleEntities.resolve([entity("stale")]);
    await staleRequest;

    expect(await getEntities("midi-1")).toEqual(fresh);
    expect(entityFetches).toBe(2);
  });
});

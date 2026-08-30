import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkBundle } from "@/lib/domain.types";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/supabase", () => ({ supabase: null }));

import { apiFetch } from "@/lib/api";
import { clearWorkDataCache, getEntities, getInsights, getWorkBundle } from "@/lib/api-client";

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

describe("saved Work open critical path", () => {
  beforeEach(() => {
    clearWorkDataCache();
    mockApiFetch.mockReset();
  });

  it("returns the durable bundle while entity and insight warmers are still unresolved", async () => {
    const entities = deferred<never[]>();
    const insights = deferred<never[]>();
    mockApiFetch.mockImplementation(async (url) => {
      if (url === "/api/v1/works/work-1") return terminalBundle();
      if (url === "/api/v1/versions/midi-1/entities") return entities.promise;
      if (url === "/api/v1/versions/midi-1/insights") return insights.promise;
      throw new Error(`Unexpected API call: ${url}`);
    });

    let openSettled = false;
    const opening = getWorkBundle("work-1").then((bundle) => {
      openSettled = true;
      return bundle;
    });

    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith("/api/v1/versions/midi-1/entities");
      expect(mockApiFetch).toHaveBeenCalledWith("/api/v1/versions/midi-1/insights");
    });
    // Give the outer async function a turn to settle. Before #710 this stays
    // false until both deferred child requests resolve, putting them directly
    // on click-to-usable latency for every cold saved-Work open.
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    expect(openSettled).toBe(true);
    expect((await opening).work.id).toBe("work-1");

    // Foreground hydration joins the same in-flight TanStack requests rather
    // than creating duplicate entity/insight calls.
    const foregroundEntities = getEntities("midi-1");
    const foregroundInsights = getInsights("midi-1");
    expect(mockApiFetch.mock.calls.filter(([url]) => url === "/api/v1/versions/midi-1/entities")).toHaveLength(1);
    expect(mockApiFetch.mock.calls.filter(([url]) => url === "/api/v1/versions/midi-1/insights")).toHaveLength(1);

    entities.resolve([]);
    insights.resolve([]);
    await Promise.all([foregroundEntities, foregroundInsights]);
  });
});

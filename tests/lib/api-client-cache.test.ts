import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkBundle } from "@/lib/domain.types";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/supabase", () => ({ supabase: null }));

import { apiFetch } from "@/lib/api";
import {
  clearWorkDataCache,
  getWorkBundle,
  startUnderstandWorkflow,
} from "@/lib/api-client";

const mockApiFetch = vi.mocked(apiFetch);

function savedBundle(): WorkBundle {
  return {
    work: {
      id: "work-1",
      project_id: "project-1",
      title: "Piece",
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
});

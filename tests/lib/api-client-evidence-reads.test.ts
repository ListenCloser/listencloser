import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, apiFetch } = vi.hoisted(() => ({
  get: vi.fn(),
  apiFetch: vi.fn(),
}));

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
vi.mock("@/lib/api", () => ({ apiFetch }));
vi.mock("@/lib/supabase", () => ({ supabase: null }));

import { clearWorkDataCache, getEntities, getInsights } from "@/lib/api-client";
import { getQueryClient } from "@/lib/query-client";

const span = {
  start_seconds: 0,
  end_seconds: 1,
  start_beat: null,
  end_beat: null,
  start_measure: null,
  end_measure: null,
};

const entity = {
  id: "00000000-0000-0000-0000-000000000001",
  version_id: "00000000-0000-0000-0000-000000000010",
  kind: "cadence" as const,
  span,
  note: null,
  chord: null,
  cadence: {
    kind: "authentic",
    chords: ["V", "I"],
    position_seconds: 1,
  },
  label: "cadence",
};

const insight = {
  id: "00000000-0000-0000-0000-000000000002",
  version_id: entity.version_id,
  kind: "harmony",
  claim: "Cadential arrival",
  span,
  entity_ids: [entity.id],
  evidence: {},
  confidence: null,
  provenance: {},
  created_at: "2026-08-30T00:00:00Z",
  created_by: null,
  produced_by_job_id: null,
};

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

describe("generated entity and insight read transport", () => {
  beforeEach(() => {
    getQueryClient().clear();
    clearWorkDataCache();
    get.mockReset();
    apiFetch.mockReset();
  });

  it("reads entities and insights through generated path operations", async () => {
    get.mockResolvedValueOnce(ok([entity])).mockResolvedValueOnce(ok([insight]));

    await expect(getEntities(entity.version_id)).resolves.toEqual([entity]);
    await expect(getInsights(entity.version_id)).resolves.toEqual([insight]);

    expect(get).toHaveBeenNthCalledWith(1, "/api/v1/versions/{version_id}/entities", {
      params: { path: { version_id: entity.version_id } },
    });
    expect(get).toHaveBeenNthCalledWith(2, "/api/v1/versions/{version_id}/insights", {
      params: { path: { version_id: entity.version_id } },
    });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fails closed when a persisted Entity omits its server-materialized id", async () => {
    const { id: _id, ...invalidEntity } = entity;
    get.mockResolvedValue(ok([invalidEntity]));

    await expect(getEntities(entity.version_id)).rejects.toThrow(
      'Invalid Entity response: missing server field "id"',
    );
  });

  it("fails closed when a persisted span omits a server-materialized coordinate", async () => {
    const { end_measure: _endMeasure, ...invalidSpan } = span;
    get.mockResolvedValue(ok([{ ...entity, span: invalidSpan }]));

    await expect(getEntities(entity.version_id)).rejects.toThrow(
      'Invalid Span response: missing server field "end_measure"',
    );
  });

  it("fails closed when a persisted Insight omits a server-materialized evidence field", async () => {
    const { evidence: _evidence, ...invalidInsight } = insight;
    get.mockResolvedValue(ok([invalidInsight]));

    await expect(getInsights(entity.version_id)).rejects.toThrow(
      'Invalid Insight response: missing server field "evidence"',
    );
  });
});

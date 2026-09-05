import { beforeEach, describe, expect, it, vi } from "vitest";

const { post } = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock("@/lib/openapi-client", () => ({
  openapiClient: { POST: post },
  requireOpenApiData: <T,>({ data, error, response }: { data?: T; error?: unknown; response: Response }): T => {
    if (data !== undefined) return data;
    const message =
      typeof error === "object" && error !== null && "error" in error
        ? (error as { error?: unknown }).error
        : undefined;
    throw new Error(typeof message === "string" ? message : `Request failed: ${response.status}`);
  },
}));

import {
  queryRhythmDensityContext,
  type RhythmDensityContextBody,
  type RhythmDensityContextResponse,
} from "@/lib/relation-api-client";

const body: RhythmDensityContextBody = {
  density_owner_version_id: "00000000-0000-0000-0000-000000000002",
  subject_start_seconds: 4,
  subject_end_seconds: 6,
  subject_origin: "user_selected",
};

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

describe("rhythm density context generated client", () => {
  beforeEach(() => post.mockReset());

  it("uses the generated Work-scoped context operation with the exact owner Version", async () => {
    const expected: RhythmDensityContextResponse = {
      status: "withheld",
      rhythm_density_insight_id: "00000000-0000-0000-0000-000000000003",
      finding: null,
      reasons: ["reference population is insufficient"],
    };
    post.mockResolvedValue(ok(expected));

    await expect(queryRhythmDensityContext("work-1", body)).resolves.toBe(expected);
    expect(post).toHaveBeenCalledWith(
      "/api/v1/works/{work_id}/relations/rhythm-density-context",
      {
        params: { path: { work_id: "work-1" } },
        body,
      },
    );
  });

  it.each(["unavailable", "withheld", "failed"] as const)(
    "returns %s as a domain state instead of a transport error",
    async (status) => {
      const expected: RhythmDensityContextResponse = {
        status,
        rhythm_density_insight_id: null,
        finding: null,
        reasons: ["evidence boundary"],
      };
      post.mockResolvedValue(ok(expected));
      await expect(queryRhythmDensityContext("work-1", body)).resolves.toEqual(expected);
    },
  );
});

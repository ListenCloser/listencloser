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
  comparePerceptualSpans,
  type PerceptualSpanComparisonBody,
  type PerceptualSpanComparisonResponse,
} from "@/lib/relation-api-client";

const body: PerceptualSpanComparisonBody = {
  source_version_id: "00000000-0000-0000-0000-000000000002",
  subject_start_seconds: 2,
  subject_end_seconds: 4,
  comparison_start_seconds: 8,
  comparison_end_seconds: 10,
};

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

describe("perceptual span comparison client", () => {
  beforeEach(() => {
    post.mockReset();
  });

  it("uses the generated Work-scoped relation operation", async () => {
    const expected: PerceptualSpanComparisonResponse = {
      status: "supported",
      evidence_report_version_id: "00000000-0000-0000-0000-000000000003",
      finding: null,
      reasons: [],
    };
    post.mockResolvedValue(ok(expected));

    const result = await comparePerceptualSpans("work-1", body);

    expect(result).toBe(expected);
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith(
      "/api/v1/works/{work_id}/relations/perceptual-span-comparison",
      {
        params: { path: { work_id: "work-1" } },
        body,
      },
    );
  });

  it.each(["unavailable", "withheld", "failed"] as const)(
    "returns the %s domain state without converting it into a client error",
    async (status) => {
      const expected: PerceptualSpanComparisonResponse = {
        status,
        evidence_report_version_id: null,
        finding: null,
        reasons: ["evidence boundary"],
      };
      post.mockResolvedValue(ok(expected));

      await expect(comparePerceptualSpans("work-1", body)).resolves.toEqual(expected);
    },
  );
});

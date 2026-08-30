import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

import { apiFetch } from "@/lib/api";
import {
  comparePerceptualSpans,
  type PerceptualSpanComparisonBody,
  type PerceptualSpanComparisonResponse,
} from "@/lib/relation-api-client";

const mockApiFetch = vi.mocked(apiFetch);

const body: PerceptualSpanComparisonBody = {
  source_version_id: "00000000-0000-0000-0000-000000000002",
  subject_start_seconds: 2,
  subject_end_seconds: 4,
  comparison_start_seconds: 8,
  comparison_end_seconds: 10,
};

describe("perceptual span comparison client", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("forwards the generated wire contract to the Work-scoped relation route", async () => {
    const expected: PerceptualSpanComparisonResponse = {
      status: "supported",
      evidence_report_version_id: "00000000-0000-0000-0000-000000000003",
      finding: null,
      reasons: [],
    };
    mockApiFetch.mockResolvedValue(expected);

    const result = await comparePerceptualSpans("work-1", body);

    expect(result).toBe(expected);
    expect(mockApiFetch).toHaveBeenCalledTimes(1);
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/works/work-1/relations/perceptual-span-comparison",
      {
        method: "POST",
        body: JSON.stringify(body),
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
      mockApiFetch.mockResolvedValue(expected);

      await expect(comparePerceptualSpans("work-1", body)).resolves.toEqual(expected);
    },
  );
});

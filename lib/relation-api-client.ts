import type { components } from "./api-types";
import { apiFetch } from "./api";

export type PerceptualSpanComparisonBody =
  components["schemas"]["PerceptualSpanComparisonBody"];
export type PerceptualSpanComparisonResponse =
  components["schemas"]["PerceptualSpanComparisonResponse"];

/**
 * Query a same-work A/B perceptual comparison without mutating Work state.
 *
 * The generated OpenAPI types remain the wire-contract source of truth. Domain
 * states such as unavailable/withheld/failed are successful typed responses;
 * callers must not reinterpret them as transport failures.
 */
export async function comparePerceptualSpans(
  workId: string,
  body: PerceptualSpanComparisonBody,
): Promise<PerceptualSpanComparisonResponse> {
  return apiFetch<PerceptualSpanComparisonResponse>(
    `/api/v1/works/${workId}/relations/perceptual-span-comparison`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

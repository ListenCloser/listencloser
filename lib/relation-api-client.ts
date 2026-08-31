import type { components } from "./api-types";
import { openapiClient, requireOpenApiData } from "./openapi-client";

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
  const result = await openapiClient.POST(
    "/api/v1/works/{work_id}/relations/perceptual-span-comparison",
    {
      params: { path: { work_id: workId } },
      body,
    },
  );
  return requireOpenApiData(result);
}

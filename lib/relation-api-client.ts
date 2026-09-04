import type { components } from "./api-types";
import { openapiClient, requireOpenApiData } from "./openapi-client";

export type PerceptualSpanComparisonBody =
  components["schemas"]["PerceptualSpanComparisonBody"];
export type PerceptualSpanComparisonResponse =
  components["schemas"]["PerceptualSpanComparisonResponse"];
export type SimilarMomentMatch = components["schemas"]["SimilarMomentMatch"];
export type SimilarMomentsMethod = components["schemas"]["SimilarMomentsMethod"];
export type SimilarMomentsObservation = components["schemas"]["SimilarMomentsObservation"];
export type SimilarMomentsBody = components["schemas"]["SimilarMomentsBody"];
export type SimilarMomentsResponse = components["schemas"]["SimilarMomentsResponse"];

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

/** Query bounded experimental same-Work neighbors for one exact selected passage. */
export async function getSimilarMoments(
  workId: string,
  body: SimilarMomentsBody,
): Promise<SimilarMomentsResponse> {
  const result = await openapiClient.POST(
    "/api/v1/works/{work_id}/relations/similar-moments",
    {
      params: { path: { work_id: workId } },
      body,
    },
  );
  return requireOpenApiData(result);
}

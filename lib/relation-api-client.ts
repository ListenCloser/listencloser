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
export type RhythmDensityContextBody =
  components["schemas"]["RhythmDensityContextBody"];
export type RhythmDensityContextResponse =
  components["schemas"]["RhythmDensityContextQueryResult"];

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

/**
 * Query literal within-Work rhythm-density context for one exact persisted
 * density-owning Version. The browser receives server-composed facts only.
 */
export async function queryRhythmDensityContext(
  workId: string,
  body: RhythmDensityContextBody,
): Promise<RhythmDensityContextResponse> {
  const result = await openapiClient.POST(
    "/api/v1/works/{work_id}/relations/rhythm-density-context",
    {
      params: { path: { work_id: workId } },
      body,
    },
  );
  return requireOpenApiData(result);
}

/** Discover a bounded experimental top set for one immutable source Version. */
export async function getMeasuredChanges(
  workId: string,
  sourceVersionId: string,
) {
  const result = await openapiClient.GET(
    "/api/v1/works/{work_id}/relations/measured-changes",
    {
      params: {
        path: { work_id: workId },
        query: { source_version_id: sourceVersionId },
      },
    },
  );
  return requireOpenApiData(result);
}

export type MeasuredChangeQueryResponse = Awaited<ReturnType<typeof getMeasuredChanges>>;
export type MeasuredChangeCandidate = NonNullable<MeasuredChangeQueryResponse["candidates"]>[number];

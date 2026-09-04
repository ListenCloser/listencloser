import type { components } from "./api-types";
import {
  openapiClient,
  requireOpenApiData,
  throwOpenApiError,
  withCurrentSupabaseAuth,
} from "./openapi-client";

export type PerceptualSpanComparisonBody =
  components["schemas"]["PerceptualSpanComparisonBody"];
export type PerceptualSpanComparisonResponse =
  components["schemas"]["PerceptualSpanComparisonResponse"];

type GroundedRelationFinding = components["schemas"]["GroundedRelationFinding"];

export type MeasuredChangeCandidate = {
  rank: number;
  boundary_seconds: number;
  before_span_seconds: [number, number];
  after_span_seconds: [number, number];
  ranking_score: number;
  changed_feature_count: number;
  changed_component_count: number;
  normalized_feature_changes: Record<string, number>;
  normalized_component_changes: Record<string, number>;
  finding: GroundedRelationFinding;
};

export type MeasuredChangeQueryResponse = {
  status: "supported" | "unavailable" | "withheld" | "failed";
  evidence_report_version_id?: string | null;
  method?: string | null;
  method_parameters: Record<string, number>;
  candidates: MeasuredChangeCandidate[];
  reasons: string[];
};

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

/**
 * Discover a small experimental top set over one immutable source Version.
 *
 * The endpoint is new in #848; the handwritten envelope here is intentionally
 * narrow and reuses the generated GroundedRelationFinding contract. The OpenAPI
 * artifact is regenerated in the same PR so this temporary path shape cannot
 * drift silently.
 */
export async function getMeasuredChanges(
  workId: string,
  sourceVersionId: string,
): Promise<MeasuredChangeQueryResponse> {
  const url = new URL(
    `/api/v1/works/${encodeURIComponent(workId)}/relations/measured-changes`,
    window.location.origin,
  );
  url.searchParams.set("source_version_id", sourceVersionId);

  const request = await withCurrentSupabaseAuth(
    new Request(url, { method: "GET", headers: { Accept: "application/json" } }),
  );
  const response = await fetch(request);
  if (!response.ok) {
    let error: unknown;
    try {
      error = await response.json();
    } catch {
      error = undefined;
    }
    throwOpenApiError(error, response);
  }
  return (await response.json()) as MeasuredChangeQueryResponse;
}

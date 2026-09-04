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

export type SimilarMomentMatch = {
  start_seconds: number;
  end_seconds: number;
  distance: number;
  component_distances: Record<string, number>;
};

export type SimilarMomentsMethod = {
  id: "perceptual_descriptor_shape";
  version: "1.0";
  dimensions: string[];
  distance: "mean_length_normalized_z_euclidean";
  candidate_window: "same_evidence_frame_count_as_query";
  overlap_exclusion: "exclude_query_overlap_and_mutually_overlapping_returned_windows";
  score_semantics: "lower_is_closer_under_this_method_not_confidence";
  semantic_claims: "none";
  parameters: Record<string, number>;
};

export type SimilarMomentsObservation = {
  source_version_id: string;
  evidence_report_version_id: string;
  evidence_report_type: "perceptual_series";
  preprocessing_version: string;
  sample_rate: number;
  query_start_seconds: number;
  query_end_seconds: number;
  max_matches: number;
  method: SimilarMomentsMethod;
  matches: SimilarMomentMatch[];
  no_match_reason?: string | null;
};

export type SimilarMomentsResponse = {
  status: "supported" | "unavailable" | "withheld" | "failed";
  evidence_report_version_id?: string | null;
  observation?: SimilarMomentsObservation | null;
  reasons: string[];
};

export type SimilarMomentsBody = {
  source_version_id: string;
  query_start_seconds: number;
  query_end_seconds: number;
  max_matches?: number;
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

/** Query bounded experimental same-Work neighbors for one exact selected passage. */
export async function getSimilarMoments(
  workId: string,
  body: SimilarMomentsBody,
): Promise<SimilarMomentsResponse> {
  const url = new URL(
    `/api/v1/works/${encodeURIComponent(workId)}/relations/similar-moments`,
    window.location.origin,
  );
  const request = await withCurrentSupabaseAuth(
    new Request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    }),
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
  return (await response.json()) as SimilarMomentsResponse;
}

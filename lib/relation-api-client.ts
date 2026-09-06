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
export type HarmonyInterpretationEngine = "lv-chordia" | "chordmini";

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
) {
  const result = await openapiClient.POST(
    "/api/v1/works/{work_id}/relations/rhythm-density-context",
    {
      params: { path: { work_id: workId } },
      body,
    },
  );
  return requireOpenApiData(result);
}

// Derive the response from the typed client operation itself. openapi-fetch's
// response helper widens tuple arrays while preserving their wire shape, so a
// second explicit component annotation would create two incompatible views of
// the same generated contract.
export type RhythmDensityContextResponse = Awaited<ReturnType<typeof queryRhythmDensityContext>>;

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

/** Generate the experimental ChordMini interpretation for exact Work Versions. */
export async function startChordMiniInterpretation(
  workId: string,
  performanceMidiVersionId: string,
  sourceAudioVersionId: string,
) {
  const result = await openapiClient.POST(
    "/api/v1/works/{work_id}/workflows/harmony-interpretation",
    {
      params: { path: { work_id: workId } },
      body: {
        performance_midi_version_id: performanceMidiVersionId,
        source_audio_version_id: sourceAudioVersionId,
        harmony_engine: "chordmini",
      },
    },
  );
  return requireOpenApiData(result);
}

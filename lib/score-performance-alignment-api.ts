import type { components } from "./api-types";
import { openapiClient, requireOpenApiData } from "./openapi-client";

export type ScorePerformanceAlignmentWorkflow = components["schemas"]["WorkflowJobResponse"];

/**
 * Queue alignment for the exact Score Version currently being shown and the
 * exact canonical performance-MIDI Version. The backend independently rechecks
 * both roles and same-Work membership before creating an idempotent Job.
 */
export async function startScorePerformanceAlignment(
  scoreVersionId: string,
  performanceVersionId: string,
  projectId: string,
): Promise<ScorePerformanceAlignmentWorkflow> {
  const result = await openapiClient.POST("/api/v1/workflows/score-performance-alignment", {
    body: {
      score_version_id: scoreVersionId,
      performance_version_id: performanceVersionId,
      project_id: projectId,
    },
  });
  return requireOpenApiData(result);
}

import { clearWorkDataCache } from "./api-client";
import { openapiClient, requireOpenApiData } from "./openapi-client";

/**
 * Prepare the measured audio evidence used by within-recording relational tools.
 * This is an implementation dependency, not a user-facing analysis surface.
 */
export async function startPerceptualSeriesWorkflow(
  versionId: string,
  projectId: string,
): Promise<string> {
  const result = await openapiClient.POST("/api/v1/workflows/create", {
    body: {
      version_id: versionId,
      project_id: projectId,
      action: "perceptual_series",
      parameters: {},
    },
  });
  const payload = requireOpenApiData(result);
  const jobId = payload.job?.id;
  if (!jobId) throw new Error("Similarity preparation response did not include a job id");
  clearWorkDataCache();
  return jobId;
}

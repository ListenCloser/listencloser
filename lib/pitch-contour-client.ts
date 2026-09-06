import { clearWorkDataCache } from "./api-client";
import { openapiClient, requireOpenApiData } from "./openapi-client";

export type PitchContourEngine = "pyin" | "pesto" | "torchcrepe";

export async function startPitchContourWorkflow(
  versionId: string,
  projectId: string,
  pitchEngine: PitchContourEngine = "pyin",
): Promise<string> {
  const result = await openapiClient.POST("/api/v1/workflows/create", {
    body: {
      version_id: versionId,
      project_id: projectId,
      action: "pitch_contour",
      parameters: { pitch_engine: pitchEngine },
    },
  });
  const payload = requireOpenApiData(result);
  const jobId = payload.job?.id;
  if (!jobId) throw new Error("Pitch contour response did not include a job id");
  clearWorkDataCache();
  return jobId;
}

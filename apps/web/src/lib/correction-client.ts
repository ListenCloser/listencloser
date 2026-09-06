import type { components } from "./api-types";
import { clearWorkDataCache } from "./api-client";
import { openapiClient, requireOpenApiData } from "./openapi-client";
import type { CorrectionReplacement } from "./piano-roll-correction";

type CorrectWorkflowBody = components["schemas"]["CorrectWorkflowBody"];

export async function startCorrectWorkflow(
  versionId: string,
  projectId: string,
  replacement: CorrectionReplacement,
): Promise<{ jobId: string }> {
  const body: CorrectWorkflowBody = {
    version_id: versionId,
    project_id: projectId,
    selection_start: replacement.selectionStart,
    selection_end: replacement.selectionEnd,
    corrected_notes: replacement.correctedNotes,
  };
  const result = await openapiClient.POST("/api/v1/workflows/correct", { body });
  const data = requireOpenApiData(result);
  const jobId = data.job.id;
  if (!jobId) throw new Error("Correction workflow did not return an exact Job id.");

  // The correction job mutates the Work graph asynchronously. Advance the
  // immutable-read cache epoch now; the session advances it again after the
  // terminal Job so the exact output Version is visible on reload.
  clearWorkDataCache();
  return { jobId };
}

import { clearWorkDataCache } from "./api-client";
import { openapiClient, requireOpenApiData } from "./openapi-client";

export type StructureMapSpan = {
  label: string;
  start_seconds: number;
  end_seconds: number;
  recurrence_of: string | null;
  similarity: number | null;
};

export type StructureMapReport = {
  schema_version: 1;
  report_type: "structure_map";
  experimental: true;
  source_version_id: string;
  duration_seconds: number;
  method: {
    id: "librosa_recurrence_novelty_v1";
    label: string;
    librosa_version: string;
    scipy_version: string;
    parameters: Record<string, string | number>;
  };
  candidate_spans: StructureMapSpan[];
  interpretation: string;
  limitations: string[];
};

export async function startStructureMapWorkflow(
  versionId: string,
  projectId: string,
): Promise<string> {
  const result = await openapiClient.POST("/api/v1/workflows/create", {
    body: {
      version_id: versionId,
      project_id: projectId,
      action: "structure_map",
      parameters: {},
    },
  });
  const payload = requireOpenApiData(result);
  const jobId = payload.job?.id;
  if (!jobId) throw new Error("Structure Map response did not include a job id");
  clearWorkDataCache();
  return jobId;
}

export async function fetchStructureMapReport(url: string): Promise<StructureMapReport> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Structure Map report failed: ${response.status}`);
  const payload = await response.json() as StructureMapReport;
  if (payload.report_type !== "structure_map" || payload.experimental !== true) {
    throw new Error("Unexpected Structure Map report contract");
  }
  return payload;
}

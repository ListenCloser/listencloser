import { clearWorkDataCache } from "./api-client";
import { openapiClient, requireOpenApiData } from "./openapi-client";

export type ProductionSpatialRelation = {
  kind: "loudness_change" | "mid_side_change" | "spectral_change" | "transient_change";
  label: string;
  method: string;
  unit: string;
  delta: number;
  start_seconds: number;
  end_seconds: number;
  from_start_seconds: number;
  from_end_seconds: number;
  to_start_seconds: number;
  to_end_seconds: number;
};

export type ProductionSpatialReport = {
  schema_version: 1;
  report_type: "production_spatial";
  experimental: true;
  source_version_id: string;
  duration_seconds: number;
  channel_count: number;
  method: {
    id: "pyloudnorm_librosa_mid_side_v1";
    label: string;
    pyloudnorm_version: string;
    librosa_version: string;
    parameters: Record<string, string | number>;
  };
  relations: ProductionSpatialRelation[];
  interpretation: string;
  limitations: string[];
};

export async function startProductionSpatialWorkflow(
  versionId: string,
  projectId: string,
): Promise<string> {
  const result = await openapiClient.POST("/api/v1/workflows/create", {
    body: {
      version_id: versionId,
      project_id: projectId,
      action: "production_spatial",
      parameters: {},
    },
  });
  const payload = requireOpenApiData(result);
  const jobId = payload.job?.id;
  if (!jobId) throw new Error("Production / Space response did not include a job id");
  clearWorkDataCache();
  return jobId;
}

export async function fetchProductionSpatialReport(url: string): Promise<ProductionSpatialReport> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Production / Space report failed: ${response.status}`);
  const payload = await response.json() as ProductionSpatialReport;
  if (payload.report_type !== "production_spatial" || payload.experimental !== true) {
    throw new Error("Unexpected Production / Space report contract");
  }
  return payload;
}

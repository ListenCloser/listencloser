import { clearWorkDataCache } from "./api-client";
import type { Job, WorkBundle } from "./domain.types";
import { openapiClient, requireOpenApiData } from "./openapi-client";

export type MelodyPlaybackSourceRef = {
  id: string;
  url: string;
};

export function findMelodyPlaybackSource(
  bundle: WorkBundle,
  sourceMidiVersionId: string,
  sourceInsightId: string,
): MelodyPlaybackSourceRef | null {
  const item = bundle.artifacts.find((candidate) => {
    const version = candidate.latest_version;
    const metadata = version?.metadata;
    return candidate.artifact.kind === "audio_rendered"
      && Boolean(candidate.signed_url)
      && metadata?.representation === "melody_playback"
      && metadata.source_midi_version_id === sourceMidiVersionId
      && metadata.source_insight_id === sourceInsightId;
  });
  return item?.latest_version && item.signed_url
    ? { id: item.latest_version.id, url: item.signed_url }
    : null;
}

export function findMelodyAuditionJob(
  bundle: WorkBundle,
  sourceMidiVersionId: string,
  sourceInsightId: string,
): Job | null {
  return bundle.jobs.find((job) => (
    job.capability.name === "melody_audition"
    && job.input_version_ids.includes(sourceMidiVersionId)
    && job.parameters?.insight_id === sourceInsightId
  )) ?? null;
}

export async function startMelodyAuditionWorkflow(
  versionId: string,
  projectId: string,
  insightId: string,
): Promise<string> {
  const result = await openapiClient.POST("/api/v1/workflows/create", {
    body: {
      version_id: versionId,
      project_id: projectId,
      action: "melody_audition",
      parameters: { insight_id: insightId },
    },
  });
  const payload = requireOpenApiData(result);
  const jobId = payload.job?.id;
  if (!jobId) throw new Error("Melody playback response did not include a job id");
  clearWorkDataCache();
  return jobId;
}

import { clearWorkDataCache } from "./api-client";
import { openapiClient, requireOpenApiData } from "./openapi-client";

export type SymbolicDetailReport = {
  schema_version: 1;
  report_type: "symbolic_detail";
  experimental: true;
  source_version_id: string;
  source_artifact_kind: "midi_performance" | "midi_corrected";
  method: {
    id: "partitura_performance_midi_v1";
    label: string;
    partitura_version: string;
    music21_version: string;
    parameters: Record<string, string | number | boolean>;
  };
  register: {
    low_midi: number;
    high_midi: number;
    low_name: string;
    high_name: string;
    median_midi: number;
    span_semitones: number;
  };
  contour: {
    basis: "onset_pitch_centroid";
    onset_count: number;
    first_centroid_midi: number;
    last_centroid_midi: number;
    net_change_semitones: number;
    slope_semitones_per_quarter: number;
  };
  interval_motion: {
    basis: "within_midi_stream_onset_centroid";
    interval_count: number;
    mean_absolute_semitones: number;
    median_absolute_semitones: number;
    repeat_fraction: number;
    step_fraction: number;
    leap_fraction: number;
    ascending_fraction: number;
    descending_fraction: number;
  };
  density: {
    note_count: number;
    duration_quarters: number;
    notes_per_quarter: number;
    window_quarters: number;
    windows: Array<{
      start_quarter: number;
      end_quarter: number;
      onset_count: number;
      note_count: number;
    }>;
  };
  texture: {
    midi_stream_count: number;
    peak_simultaneous_notes: number;
    mean_simultaneous_notes: number;
    polyphonic_time_fraction: number;
  };
  voice_motion: {
    basis: "midi_stream_shared_onsets";
    status: "supported" | "unavailable";
    analyzable_transition_count: number;
    similar_direction_fraction: number | null;
    contrary_direction_fraction: number | null;
    oblique_like_fraction: number | null;
    reason: string | null;
  };
  interpretation: string;
  limitations: string[];
};

export async function startSymbolicDetailWorkflow(
  versionId: string,
  projectId: string,
): Promise<string> {
  const result = await openapiClient.POST("/api/v1/workflows/create", {
    body: {
      version_id: versionId,
      project_id: projectId,
      action: "symbolic_detail",
      parameters: {},
    },
  });
  const payload = requireOpenApiData(result);
  const jobId = payload.job?.id;
  if (!jobId) throw new Error("Symbolic detail response did not include a job id");
  clearWorkDataCache();
  return jobId;
}

export async function fetchSymbolicDetailReport(url: string): Promise<SymbolicDetailReport> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Symbolic detail report failed: ${response.status}`);
  const payload = await response.json() as SymbolicDetailReport;
  if (payload.report_type !== "symbolic_detail" || payload.experimental !== true) {
    throw new Error("Unexpected symbolic detail report contract");
  }
  return payload;
}

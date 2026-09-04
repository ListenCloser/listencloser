import { delay, http, HttpResponse } from "msw";
import { sampleWavBase64 } from "@/app/_test-support/msw/fixtures/sample-wav";

const JOB_ID = "mock-production-spatial-job";
const WORKFLOW_ID = "mock-production-spatial-workflow";
const REPORT_VERSION_ID = "mock-production-spatial-report-version";
let reportReady = false;

export function productionSpatialReportReady(): boolean {
  return reportReady;
}

export function productionSpatialReportArtifact(now: string, sourceVersionId: string) {
  const metadata = {
    report_type: "production_spatial",
    schema_version: 1,
    experimental: true,
    source_version_id: sourceVersionId,
    method: "pyloudnorm_librosa_mid_side_v1",
    relation_count: 4,
    channel_count: 2,
    semantic_labels: false,
    issue: 1179,
  };
  const version = {
    id: REPORT_VERSION_ID,
    artifact_id: "mock-production-spatial-report-artifact",
    storage_bucket: "artifacts",
    storage_key: "mock/production-spatial.json",
    parent_version_id: sourceVersionId,
    lineage: [sourceVersionId],
    byte_size: 512,
    sha256: null,
    label: "Experimental Production / Space",
    metadata,
    created_at: now,
    created_by: "mock-user-1",
    produced_by_job_id: JOB_ID,
  };
  return {
    artifact: {
      id: "mock-production-spatial-report-artifact",
      work_id: "mock-work-1",
      kind: "analysis_report",
      mime_type: "application/json",
      created_at: now,
    },
    versions: [version],
    latest_version: version,
    signed_url: "/__test/production-spatial-report",
  };
}

function sourceArtifact(now: string) {
  const version = {
    id: "mock-version-1",
    artifact_id: "mock-artifact-1",
    storage_bucket: "artifacts",
    storage_key: "test/mock-version-1.wav",
    parent_version_id: null,
    lineage: [],
    byte_size: 44000,
    sha256: null,
    label: "test.wav",
    metadata: {},
    created_at: now,
    created_by: "mock-user-1",
    produced_by_job_id: null,
  };
  return {
    artifact: {
      id: "mock-artifact-1",
      work_id: "mock-work-1",
      kind: "audio_original",
      mime_type: "audio/wav",
      created_at: now,
    },
    versions: [version],
    latest_version: version,
    signed_url: `data:audio/wav;base64,${sampleWavBase64}`,
  };
}

const report = {
  schema_version: 1,
  report_type: "production_spatial",
  experimental: true,
  source_version_id: "mock-version-1",
  duration_seconds: 12,
  channel_count: 2,
  method: {
    id: "pyloudnorm_librosa_mid_side_v1",
    label: "BS.1770 loudness + mid/side + librosa window comparison",
    pyloudnorm_version: "0.2.0",
    librosa_version: "0.11.0",
    parameters: {
      sample_rate: 48000,
      window_seconds: 3,
      minimum_window_seconds: 1,
      n_fft: 2048,
      hop_length: 512,
    },
  },
  windows: [],
  relations: [
    {
      kind: "loudness_change",
      label: "Loudness",
      method: "pyloudnorm BS.1770 integrated loudness per fixed window; largest adjacent delta",
      unit: "LUFS",
      delta: 8.2,
      start_seconds: 3,
      end_seconds: 9,
      from_start_seconds: 3,
      from_end_seconds: 6,
      to_start_seconds: 6,
      to_end_seconds: 9,
    },
    {
      kind: "mid_side_change",
      label: "Side energy share",
      method: "side RMS² / (mid RMS² + side RMS²) per fixed stereo window; largest adjacent delta",
      unit: "percentage points",
      delta: 22.5,
      start_seconds: 3,
      end_seconds: 9,
      from_start_seconds: 3,
      from_end_seconds: 6,
      to_start_seconds: 6,
      to_end_seconds: 9,
    },
    {
      kind: "spectral_change",
      label: "Spectral centroid",
      method: "librosa spectral centroid mean per fixed window; largest adjacent delta",
      unit: "Hz",
      delta: 412.4,
      start_seconds: 3,
      end_seconds: 9,
      from_start_seconds: 3,
      from_end_seconds: 6,
      to_start_seconds: 6,
      to_end_seconds: 9,
    },
    {
      kind: "transient_change",
      label: "Onset strength",
      method: "librosa onset-strength mean per fixed window; largest adjacent delta",
      unit: "librosa onset strength",
      delta: 0.317,
      start_seconds: 3,
      end_seconds: 9,
      from_start_seconds: 3,
      from_end_seconds: 6,
      to_start_seconds: 6,
      to_end_seconds: 9,
    },
  ],
  interpretation: "Each relation compares adjacent fixed windows under the named measurement method. Values are literal measurements, not semantic production labels or importance scores.",
  limitations: [
    "Relations are local adjacent-window comparisons and do not identify sections or causes.",
  ],
};

export const productionSpatialHandlers = [
  http.post("/api/v1/workflows/create", async ({ request }) => {
    const body = await request.json() as { action?: string; version_id?: string };
    if (body.action !== "production_spatial") return undefined;
    reportReady = true;
    await delay(50);
    return HttpResponse.json({
      workflow: {
        id: WORKFLOW_ID,
        project_id: "mock-project-1",
        kind: "understand",
        target_version_id: body.version_id ?? "mock-version-1",
        parameters: {},
        created_at: new Date().toISOString(),
      },
      job: {
        id: JOB_ID,
        workflow_id: WORKFLOW_ID,
        capability: {
          name: "production_spatial",
          version: "1.0",
          accepted_input_kinds: [],
          produces_output_kinds: [],
          parameters: {},
          failure_modes: [],
        },
        lifecycle: {
          current: "queued",
          progress: 0,
          message: "queued",
          stages: [],
          retry_count: 0,
          max_retries: 3,
          lease_expires_at: null,
          started_at: null,
          completed_at: null,
        },
        input_version_ids: [body.version_id ?? "mock-version-1"],
        output_version_ids: [],
        parameters: {},
        cache_key: null,
        error: null,
        error_details: {},
        provenance: {},
        created_at: new Date().toISOString(),
        created_by: "mock-user-1",
      },
    });
  }),
  http.get(`/api/v1/jobs/${JOB_ID}`, async () => {
    await delay(100);
    return HttpResponse.json({
      id: JOB_ID,
      workflow_id: WORKFLOW_ID,
      capability: "production_spatial",
      stage: "succeeded",
      progress: 1,
      message: "production/spatial lens ready",
      error: null,
      input_version_ids: ["mock-version-1"],
      output_version_ids: [REPORT_VERSION_ID],
    });
  }),
  http.get("/api/v1/works/:workId", () => {
    if (!reportReady) return undefined;
    const now = new Date().toISOString();
    return HttpResponse.json({
      work: {
        id: "mock-work-1",
        project_id: "mock-project-1",
        title: "Test Work",
        composer: null,
        created_at: now,
        updated_at: now,
      },
      jobs: [],
      artifacts: [
        sourceArtifact(now),
        productionSpatialReportArtifact(now, "mock-version-1"),
      ],
    });
  }),
  http.get("/__test/production-spatial-report", () => HttpResponse.json(report)),
];

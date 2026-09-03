import { http, HttpResponse } from "msw";

const MOCK_STORAGE_KEY = "test/mock-version-1.wav";
const FAILURE_FIXTURE_NAME = "failure-status.m4a";
const FAILURE_VERSION_ID = "mock-version-failure";

export const directUploadHandlers = [
  http.post("/api/v1/projects/:projectId/artifacts/upload-intent", async () => {
    return HttpResponse.json({
      bucket: "artifacts",
      storage_key: MOCK_STORAGE_KEY,
      token: "mock-signed-upload-token",
      max_bytes: 100 * 1024 * 1024,
    });
  }),

  http.put(/\/storage\/v1\/object\/upload\/sign\//, async () => {
    return HttpResponse.json({ Key: `artifacts/${MOCK_STORAGE_KEY}` });
  }),

  http.post("/api/v1/projects/:projectId/artifacts/finalize-upload", async ({ request }) => {
    const now = new Date().toISOString();
    const body = await request.json() as { filename?: string };
    const versionId = body.filename === FAILURE_FIXTURE_NAME ? FAILURE_VERSION_ID : "mock-version-1";
    return HttpResponse.json({
      artifact: {
        id: "mock-artifact-1",
        work_id: "mock-work-1",
        kind: "audio_original",
        mime_type: "audio/wav",
        created_at: now,
      },
      version: {
        id: versionId,
        artifact_id: "mock-artifact-1",
        storage_bucket: "artifacts",
        storage_key: MOCK_STORAGE_KEY,
        parent_version_id: null,
        lineage: [],
        byte_size: 44000,
        sha256: null,
        label: "",
        metadata: {},
        created_at: now,
        created_by: null,
        produced_by_job_id: null,
      },
    });
  }),
];

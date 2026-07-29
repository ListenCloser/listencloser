import { http, HttpResponse, delay } from "msw";
import { sampleWavBase64, sampleWavOutputBase64 } from "@/tests/fixtures/sample-wav";
import { pitchToName } from "@/lib/notes";

const SCALE = [60, 62, 64, 65, 67, 69, 71, 72];
const fakeNotes = Array.from({ length: 42 }, (_, i) => {
  const pitch = SCALE[i % SCALE.length];
  const start = i * 0.25;
  const end = start + 0.22;
  return { pitch, start, end, velocity: 80 + Math.floor(Math.random() * 40) };
});

const wavBase64 = sampleWavBase64;

export const handlers = [
  http.post("/api/music/enhance", async () => {
    await delay(200);
    return HttpResponse.json({ wav_base64: wavBase64, url: null });
  }),

  http.post("/api/music/transcribe", async () => {
    await delay(1500);
    const midiBase64 = "TVRoZAAAAAYAAAABAAIBTVRyawAAAAwAAQDIz+oAQM3P6v4A";
    return HttpResponse.json({
      notes: fakeNotes,
      num_notes: fakeNotes.length,
      midi_base64: midiBase64,
      wav_base64: sampleWavOutputBase64,
      midi_url: "https://example.com/mock-transcription.mid",
      wav_url: "https://example.com/mock-transcription.wav",
      analysis: {
        key: { tonic: "C", mode: "major", confidence: 0.8 },
        tempo: { bpm: 120, confidence: 0.92 },
        time_signature: { numerator: 4, denominator: 4, confidence: 0.95 },
      },
    });
  }),

  http.post("/api/music/analyze", async () => {
    await delay(1200);
    return HttpResponse.json({
      key: { tonic: "A", mode: "minor", confidence: 0.82 },
      tempo: { bpm: 112, confidence: 0.88 },
      time_signature: { numerator: 4, denominator: 4, confidence: 0.9 },
      chords: [
        { root: "A", quality: "m", start: 0.0, end: 2.0 },
        { root: "F", quality: "M", start: 2.0, end: 4.0 },
        { root: "C", quality: "M", start: 4.0, end: 6.0 },
        { root: "G", quality: "M", start: 6.0, end: 8.0 },
        { root: "A", quality: "m", start: 8.0, end: 10.0 },
      ],
    });
  }),

  http.post("/api/music/library", async ({ request }) => {
    await delay(200);
    const body = (await request.json()) as Record<string, unknown>;
    const id = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
    return HttpResponse.json({ id, title: body.title ?? "Untitled", created_at: new Date().toISOString() });
  }),

  http.get("/api/music/library", async () => {
    await delay(200);
    return HttpResponse.json({ items: [] });
  }),

  http.delete("/api/music/library/transcription/:recordId", async () => {
    await delay(150);
    return HttpResponse.json({ status: "deleted" });
  }),

  // ── Domain API v1 ──────────────────────────────────────────

  http.post("/api/v1/projects", async () => {
    await delay(150);
    return HttpResponse.json({
      id: "mock-project-1", owner_id: "mock-user-1", name: "Test Project",
      description: "", created_at: new Date().toISOString(), updated_at: new Date().toISOString(), archived_at: null,
    });
  }),

  http.get("/api/v1/projects", async () => {
    return HttpResponse.json([{ id: "mock-project-1", owner_id: "mock-user-1", name: "Test Project", description: "", created_at: new Date().toISOString(), updated_at: new Date().toISOString(), archived_at: null }]);
  }),

  http.post("/api/v1/projects/:projectId/works", async () => {
    await delay(100);
    return HttpResponse.json({ id: "mock-work-1", project_id: "mock-project-1", title: "Test Work", composer: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
  }),

  http.post("/api/v1/projects/:projectId/artifacts/upload", async () => {
    await delay(200);
    return HttpResponse.json({
      artifact: { id: "mock-artifact-1", work_id: "mock-work-1", kind: "audio_original", mime_type: "audio/wav", created_at: new Date().toISOString() },
      version: { id: "mock-version-1", artifact_id: "mock-artifact-1", storage_bucket: "artifacts", storage_key: "test/mock-version-1.wav", parent_version_id: null, lineage: [], byte_size: 44000, sha256: null, label: "", metadata: {}, created_at: new Date().toISOString(), created_by: null, produced_by_job_id: null },
    });
  }),

  http.post("/api/v1/workflows/understand", async () => {
    await delay(100);
    return HttpResponse.json({
      workflow: { id: "mock-workflow-1", project_id: "mock-project-1", kind: "understand", target_version_id: null, parameters: {}, created_at: new Date().toISOString() },
      job: { id: "mock-job-1", workflow_id: "mock-workflow-1", capability: { name: "transcribe", version: "1.0" }, lifecycle: { current: "queued", progress: 0, message: "Starting transcription...", stages: [], retry_count: 0, max_retries: 3, lease_expires_at: null, started_at: null, completed_at: null }, input_version_ids: ["mock-version-1"], output_version_ids: [], parameters: {}, cache_key: null, error: null, error_details: {}, provenance: {}, created_at: new Date().toISOString(), created_by: null },
    });
  }),

  http.get("/api/v1/jobs/:jobId", async () => {
    await delay(300);
    return HttpResponse.json({
      id: "mock-job-1", workflow_id: "mock-workflow-1", capability: { name: "transcribe", version: "1.0" },
      lifecycle: { current: "succeeded", progress: 100, message: "Transcription complete", stages: [], retry_count: 0, max_retries: 3, lease_expires_at: null, started_at: new Date().toISOString(), completed_at: new Date().toISOString() },
      input_version_ids: ["mock-version-1"], output_version_ids: ["mock-midi-version"], parameters: {}, cache_key: null, error: null, error_details: {}, provenance: { metadata: { bpm: 120, note_count: 42 } }, created_at: new Date().toISOString(), created_by: null,
    });
  }),

  http.get("/api/v1/versions/:versionId/entities", async () => {
    return HttpResponse.json(fakeNotes.map((n, i) => ({
      id: `mock-entity-${i}`, version_id: "mock-midi-version", kind: "note",
      span: { start_seconds: n.start, end_seconds: n.end },
      note: { pitch: n.pitch, start_seconds: n.start, end_seconds: n.end, velocity: n.velocity, voice: 0 },
      chord: null, cadence: null, label: pitchToName(n.pitch),
    })));
  }),

  http.get("/api/v1/versions/:versionId/insights", async () => {
    return HttpResponse.json([]);
  }),
];

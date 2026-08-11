import { http, HttpResponse, delay } from "msw";
import { sampleWavBase64, sampleWavOutputBase64 } from "@/tests/fixtures/sample-wav";
import { pitchToName } from "@/lib/notes";

const SCALE = [60, 62, 64, 65, 67, 69, 71, 72];
const fakeNotes = Array.from({ length: 42 }, (_, i) => {
  const pitch = SCALE[i % SCALE.length];
  const start = i * 0.25;
  const end = start + 0.22;
  return { pitch, start, end, velocity: 80 + (i % 40) };
});

const wavBase64 = sampleWavBase64;

export const handlers = [
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

  http.get("/api/v1/projects/:projectId/works", async () => {
    return HttpResponse.json([
      { id: "mock-work-1", project_id: "mock-project-1", title: "Test Work", composer: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
    ]);
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
      job: { id: "mock-job-1", workflow_id: "mock-workflow-1", capability: { name: "understand", version: "1.0" }, lifecycle: { current: "queued", progress: 0, message: "Understanding audio...", stages: [], retry_count: 0, max_retries: 3, lease_expires_at: null, started_at: null, completed_at: null }, input_version_ids: ["mock-version-1"], output_version_ids: [], parameters: {}, cache_key: null, error: null, error_details: {}, provenance: {}, created_at: new Date().toISOString(), created_by: null },
    });
  }),

  http.get("/api/v1/jobs/:jobId", async ({ params }) => {
    await delay(300);
    const jobId = String(params.jobId);
    const capability = "understand";
    const outputs = ["mock-midi-version", "mock-audio-version", "mock-score-version"];
    return HttpResponse.json({
      id: jobId, workflow_id: "mock-workflow-1", capability,
      stage: "succeeded", progress: 1, message: `${capability} complete`, error: null,
      input_version_ids: ["mock-version-1"], output_version_ids: outputs,
    });
  }),

  http.get("/api/v1/versions/:versionId", async ({ params }) => {
    const id = String(params.versionId);
    const kind = id.includes("midi") ? "midi_performance" : id.includes("score") ? "musicxml_score" : "audio_rendered";
    const musicxml = `<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1"><part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note></measure></part></score-partwise>`;
    const signedUrl = kind === "musicxml_score"
      ? `data:application/xml,${encodeURIComponent(musicxml)}`
      : kind === "audio_rendered" ? `data:audio/wav;base64,${sampleWavOutputBase64}` : "https://example.com/mock.mid";
    return HttpResponse.json({
      version: { id, artifact_id: `artifact-${id}`, storage_bucket: "artifacts", storage_key: `mock/${id}`, parent_version_id: null, lineage: [], byte_size: 100, sha256: null, label: id, metadata: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-job-1" },
      artifact: { id: `artifact-${id}`, work_id: "mock-work-1", kind, mime_type: "application/octet-stream", created_at: new Date().toISOString() },
      signed_url: signedUrl,
    });
  }),

  http.get("/api/v1/works/:workId", async () => {
    const now = new Date().toISOString();
    const musicxml = `<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1"><part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note></measure></part></score-partwise>`;
    const item = (id: string, kind: string, signedUrl: string) => ({
      artifact: { id: `artifact-${id}`, work_id: "mock-work-1", kind, mime_type: "application/octet-stream", created_at: now },
      versions: [{ id, artifact_id: `artifact-${id}`, storage_bucket: "artifacts", storage_key: `mock/${id}`, parent_version_id: null, lineage: [], byte_size: 100, sha256: null, label: id, metadata: {}, created_at: now, created_by: "mock-user-1", produced_by_job_id: "mock-job-1" }],
      latest_version: { id, artifact_id: `artifact-${id}`, storage_bucket: "artifacts", storage_key: `mock/${id}`, parent_version_id: null, lineage: [], byte_size: 100, sha256: null, label: id, metadata: {}, created_at: now, created_by: "mock-user-1", produced_by_job_id: "mock-job-1" },
      signed_url: signedUrl,
    });
    return HttpResponse.json({
      work: { id: "mock-work-1", project_id: "mock-project-1", title: "Test Work", composer: null, created_at: now, updated_at: now },
      jobs: [],
      artifacts: [
        item("mock-version-1", "audio_original", `data:audio/wav;base64,${sampleWavBase64}`),
        item("mock-midi-version", "midi_performance", "https://example.com/mock.mid"),
        item("mock-audio-version", "audio_rendered", `data:audio/wav;base64,${sampleWavOutputBase64}`),
        item("mock-score-version", "musicxml_score", `data:application/xml,${encodeURIComponent(musicxml)}`),
      ],
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
    const span = { start_seconds: null, end_seconds: null, start_beat: null, end_beat: null, start_measure: null, end_measure: null };
    return HttpResponse.json([
      { id: "key-insight", version_id: "mock-midi-version", kind: "key", claim: "Key: A minor", span, entity_ids: [], evidence: { tonic: "A", mode: "minor" }, confidence: 0.82, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "tempo-insight", version_id: "mock-midi-version", kind: "tempo", claim: "Tempo: 112 BPM", span, entity_ids: [], evidence: { bpm: 112 }, confidence: 0.88, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "time-insight", version_id: "mock-midi-version", kind: "time_signature", claim: "Time Signature: 4/4", span, entity_ids: [], evidence: { numerator: 4, denominator: 4 }, confidence: 0.9, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
    ]);
  }),
];

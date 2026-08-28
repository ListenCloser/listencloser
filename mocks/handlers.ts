import { http, HttpResponse, delay } from "msw";
import { sampleWavBase64, sampleWavOutputBase64 } from "@/mocks/fixtures/sample-wav";
import { pitchToName } from "@/lib/notes";

const SCALE = [60, 62, 64, 65, 67, 69, 71, 72];
const fakeNotes = Array.from({ length: 42 }, (_, i) => {
  const pitch = SCALE[i % SCALE.length];
  const start = i * 0.25;
  const end = start + 0.22;
  return { pitch, start, end, velocity: 80 + (i % 40) };
});

const wavBase64 = sampleWavBase64;

const PITCH_STEPS = ["C", "D", "E", "F", "G", "A"];
const musicxml = `<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1"><part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list><part id="P1">${PITCH_STEPS.map(
  (step, i) =>
    `<measure number="${i + 1}"><attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><note><pitch><step>${step}</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note></measure>`,
).join("")}</part></score-partwise>`;

const measureStartsSeconds = [0, 2, 4, 6, 8, 10];

export const handlers = [
  // ── Domain API v1 ──────────────────────────────────────────

  http.get("/api/health/live", () => HttpResponse.json({ status: "alive" })),
  http.get("/api/health/ready", () => HttpResponse.json({ status: "ready", supabase: true })),
  http.get("/api/health/queue", () => HttpResponse.json({ status: "ready", workers: 1, queued: 0, running: 0, stale_leases: 0 })),

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

  http.post("/api/v1/jobs/:jobId/cancel", async ({ params }) => {
    return HttpResponse.json({
      id: String(params.jobId), workflow_id: "mock-workflow-1", capability: "understand",
      stage: "cancelled", progress: 0.5, message: "cancelled by user", error: null,
      input_version_ids: ["mock-version-1"], output_version_ids: [],
    });
  }),

  http.post("/api/v1/jobs/:jobId/retry", async ({ params }) => {
    return HttpResponse.json({
      id: String(params.jobId), workflow_id: "mock-workflow-1", capability: "understand",
      stage: "queued", progress: 0, message: "queued for manual retry", error: null,
      input_version_ids: ["mock-version-1"], output_version_ids: [],
    });
  }),

  http.get("/api/v1/versions/:versionId", async ({ params }) => {
    const id = String(params.versionId);
    const kind = id.includes("rendered-score") ? "rendered_score" : id.includes("midi") ? "midi_performance" : id.includes("score") ? "musicxml_score" : "audio_rendered";
    const signedUrl = kind === "musicxml_score"
      ? `data:application/xml,${encodeURIComponent(musicxml)}`
      : kind === "audio_rendered" || kind === "rendered_score" ? `data:audio/wav;base64,${sampleWavOutputBase64}` : "https://example.com/mock.mid";
    return HttpResponse.json({
      version: { id, artifact_id: `artifact-${id}`, storage_bucket: "artifacts", storage_key: `mock/${id}`, parent_version_id: null, lineage: [], byte_size: 100, sha256: null, label: id, metadata: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-job-1" },
      artifact: { id: `artifact-${id}`, work_id: "mock-work-1", kind, mime_type: "application/octet-stream", created_at: new Date().toISOString() },
      signed_url: signedUrl,
    });
  }),

  http.get("/api/v1/works/:workId", async () => {
    const now = new Date().toISOString();
    const item = (id: string, kind: string, signedUrl: string, metadata: Record<string, unknown> = {}) => ({
      artifact: { id: `artifact-${id}`, work_id: "mock-work-1", kind, mime_type: "application/octet-stream", created_at: now },
      versions: [{ id, artifact_id: `artifact-${id}`, storage_bucket: "artifacts", storage_key: `mock/${id}`, parent_version_id: null, lineage: [], byte_size: 100, sha256: null, label: id, metadata, created_at: now, created_by: "mock-user-1", produced_by_job_id: "mock-job-1" }],
      latest_version: { id, artifact_id: `artifact-${id}`, storage_bucket: "artifacts", storage_key: `mock/${id}`, parent_version_id: null, lineage: [], byte_size: 100, sha256: null, label: id, metadata, created_at: now, created_by: "mock-user-1", produced_by_job_id: "mock-job-1" },
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
        item("mock-rendered-score-version", "rendered_score", `data:audio/wav;base64,${sampleWavOutputBase64}`, { measure_starts_seconds: measureStartsSeconds }),
      ],
    });
  }),

  http.delete("/api/v1/works/:workId", async ({ params }) => {
    await delay(100);
    return HttpResponse.json({ deleted: String(params.workId) });
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
    const nullSpan = { start_seconds: null, end_seconds: null, start_beat: null, end_beat: null, start_measure: null, end_measure: null };
    const makeSpan = (start: number, end: number) => ({ start_seconds: start, end_seconds: end, start_beat: null, end_beat: null, start_measure: null, end_measure: null });
    return HttpResponse.json([
      { id: "key-insight", version_id: "mock-midi-version", kind: "key", claim: "Key: A minor", span: nullSpan, entity_ids: [], evidence: { tonic: "A", mode: "minor" }, confidence: 0.82, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "tempo-insight", version_id: "mock-midi-version", kind: "tempo", claim: "Tempo: 112 BPM", span: nullSpan, entity_ids: [], evidence: { bpm: 112 }, confidence: 0.88, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "time-insight", version_id: "mock-midi-version", kind: "time_signature", claim: "Time Signature: 4/4", span: nullSpan, entity_ids: [], evidence: { numerator: 4, denominator: 4 }, confidence: 0.9, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "density-insight", version_id: "mock-midi-version", kind: "rhythm_density", claim: "Observed note-onset density varies across the recording", span: nullSpan, entity_ids: [], evidence: { windows: [{ start: 0.5, end: 1, density: 2 }, { start: 2, end: 2.5, density: 8 }] }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "melody-peak-insight", version_id: "mock-midi-version", kind: "melody_register_peak", claim: "Highest observed melody register around 0:02", span: makeSpan(2.5, 3.1), entity_ids: [], evidence: { pitch: 84, note: "C6" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "chord-1", version_id: "mock-midi-version", kind: "chord", claim: "C maj", span: makeSpan(0, 2), entity_ids: [], evidence: { root: "C", quality: "maj", start_seconds: 0, end_seconds: 2 }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "chord-2", version_id: "mock-midi-version", kind: "chord", claim: "G min", span: makeSpan(2, 4), entity_ids: [], evidence: { root: "G", quality: "min", start_seconds: 2, end_seconds: 4 }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "chord-3", version_id: "mock-midi-version", kind: "chord", claim: "F maj", span: makeSpan(4, 6), entity_ids: [], evidence: { root: "F", quality: "maj", start_seconds: 4, end_seconds: 6 }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "chord-4", version_id: "mock-midi-version", kind: "chord", claim: "C maj", span: makeSpan(6, 8), entity_ids: [], evidence: { root: "C", quality: "maj", start_seconds: 6, end_seconds: 8 }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "chord-5", version_id: "mock-midi-version", kind: "chord", claim: "G7", span: makeSpan(8, 10), entity_ids: [], evidence: { root: "G", quality: "7", start_seconds: 8, end_seconds: 10 }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "chord-6", version_id: "mock-midi-version", kind: "chord", claim: "C maj", span: makeSpan(10, 12), entity_ids: [], evidence: { root: "C", quality: "maj", start_seconds: 10, end_seconds: 12 }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "rn-1", version_id: "mock-midi-version", kind: "roman_numeral", claim: "I (A minor)", span: makeSpan(0, 2), entity_ids: [], evidence: { numeral: "I", degree: 1, quality: "major", start_seconds: 0, end_seconds: 2, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "rn-2", version_id: "mock-midi-version", kind: "roman_numeral", claim: "v (A minor)", span: makeSpan(2, 4), entity_ids: [], evidence: { numeral: "v", degree: 5, quality: "minor", start_seconds: 2, end_seconds: 4, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "rn-3", version_id: "mock-midi-version", kind: "roman_numeral", claim: "iv (A minor)", span: makeSpan(4, 6), entity_ids: [], evidence: { numeral: "iv", degree: 4, quality: "minor", start_seconds: 4, end_seconds: 6, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "rn-4", version_id: "mock-midi-version", kind: "roman_numeral", claim: "I (A minor)", span: makeSpan(6, 8), entity_ids: [], evidence: { numeral: "I", degree: 1, quality: "major", start_seconds: 6, end_seconds: 8, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "rn-5", version_id: "mock-midi-version", kind: "roman_numeral", claim: "V7 (A minor)", span: makeSpan(8, 10), entity_ids: [], evidence: { numeral: "V7", degree: 5, quality: "major", start_seconds: 8, end_seconds: 10, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "rn-6", version_id: "mock-midi-version", kind: "roman_numeral", claim: "I (A minor)", span: makeSpan(10, 12), entity_ids: [], evidence: { numeral: "I", degree: 1, quality: "major", start_seconds: 10, end_seconds: 12, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "hf-1", version_id: "mock-midi-version", kind: "harmonic_function", claim: "TONIC (I)", span: makeSpan(0, 2), entity_ids: [], evidence: { function: "TONIC", numeral: "I", start_seconds: 0, end_seconds: 2, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "hf-2", version_id: "mock-midi-version", kind: "harmonic_function", claim: "DOMINANT (v)", span: makeSpan(2, 4), entity_ids: [], evidence: { function: "DOMINANT", numeral: "v", start_seconds: 2, end_seconds: 4, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "hf-3", version_id: "mock-midi-version", kind: "harmonic_function", claim: "SUBDOMINANT (iv)", span: makeSpan(4, 6), entity_ids: [], evidence: { function: "SUBDOMINANT", numeral: "iv", start_seconds: 4, end_seconds: 6, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "hf-4", version_id: "mock-midi-version", kind: "harmonic_function", claim: "TONIC (I)", span: makeSpan(6, 8), entity_ids: [], evidence: { function: "TONIC", numeral: "I", start_seconds: 6, end_seconds: 8, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "hf-5", version_id: "mock-midi-version", kind: "harmonic_function", claim: "DOMINANT (V7)", span: makeSpan(8, 10), entity_ids: [], evidence: { function: "DOMINANT", numeral: "V7", start_seconds: 8, end_seconds: 10, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
      { id: "hf-6", version_id: "mock-midi-version", kind: "harmonic_function", claim: "TONIC (I)", span: makeSpan(10, 12), entity_ids: [], evidence: { function: "TONIC", numeral: "I", start_seconds: 10, end_seconds: 12, key_context: "A minor" }, confidence: null, provenance: {}, created_at: new Date().toISOString(), created_by: "mock-user-1", produced_by_job_id: "mock-analysis-job" },
    ]);
  }),

  http.post("/api/v1/ask", async () => {
    await delay(250);
    return HttpResponse.json({
      answer: "This passage stays centered on the tonic, with a gentle stepwise descent that keeps the motion gentle before the phrase lands on the downbeat.",
      references: [
        { type: "time", start: 4, end: 8, domain: "performance" },
        { type: "measure", start: 2, end: 4 },
        { type: "notes", ids: ["mock-entity-16", "mock-entity-17"] },
        { type: "insight", id: "key-insight" },
      ],
      suggestedActions: [
        { type: "show_representation", representationId: "score" },
        { type: "loop", start: 4, end: 8, domain: "performance" },
        { type: "seek", seconds: 4, domain: "performance" },
      ],
    });
  }),
];

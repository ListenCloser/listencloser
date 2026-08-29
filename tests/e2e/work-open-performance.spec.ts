import { expect, test, type Page } from "@playwright/test";
import { sampleWavOutputBase64 } from "@/mocks/fixtures/sample-wav";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

type FetchKind =
  | "work_list"
  | "work_bundle"
  | "entities"
  | "insights"
  | "score_xml"
  | "audio"
  | "other";

type FetchSample = {
  kind: FetchKind;
  method: string;
  started_ms: number;
  duration_ms: number;
  status: number;
};

type OpenSample = {
  label: string;
  source_ready_ms: number;
  evidence_ready_ms: number;
  workspace_artifacts_ready_ms: number;
  score_render_ready_ms: number;
  fetch_counts: Record<FetchKind, number>;
};

const performanceScoreXml = `<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>1</divisions><key><fifths>-1</fifths></key><time><beats>3</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>3</duration><type>half</type><dot/></note>
    </measure>
    <measure number="2"><note><pitch><step>F</step><octave>4</octave></pitch><duration>3</duration><type>half</type><dot/></note></measure>
  </part>
</score-partwise>`;

function installPerformanceFixtureScript() {
  return ({ audioBase64, scoreXml }: { audioBase64: string; scoreXml: string }) => {
    type WindowWithPerf = Window & {
      __workOpenPerfFetches?: FetchSample[];
    };

    const target = window as WindowWithPerf;
    const fetchSamples: FetchSample[] = [];
    target.__workOpenPerfFetches = fetchSamples;
    const originalFetch = window.fetch.bind(window);

    const classify = (url: string): FetchKind => {
      if (url.includes("/api/v1/projects/mock-project-1/works")) return "work_list";
      if (url.includes("/api/v1/works/")) return "work_bundle";
      if (url.includes("/entities")) return "entities";
      if (url.includes("/insights")) return "insights";
      if (url.startsWith("data:application/xml")) return "score_xml";
      if (url.startsWith("data:audio/")) return "audio";
      return "other";
    };

    const json = (value: unknown) => new Response(JSON.stringify(value), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

    const workTwoBundle = () => {
      const now = new Date().toISOString();
      const version = (
        id: string,
        artifactId: string,
        metadata: Record<string, unknown> = {},
      ) => ({
        id,
        artifact_id: artifactId,
        storage_bucket: "artifacts",
        storage_key: `perf/${id}`,
        parent_version_id: null,
        lineage: [],
        byte_size: 100,
        sha256: null,
        label: id,
        metadata,
        created_at: now,
        created_by: "mock-user-1",
        produced_by_job_id: "perf-job-2",
      });
      const item = (
        id: string,
        kind: string,
        signedUrl: string,
        metadata: Record<string, unknown> = {},
      ) => {
        const artifactId = `artifact-${id}`;
        const latest = version(id, artifactId, metadata);
        return {
          artifact: {
            id: artifactId,
            work_id: "mock-work-2",
            kind,
            mime_type: "application/octet-stream",
            created_at: now,
          },
          versions: [latest],
          latest_version: latest,
          signed_url: signedUrl,
        };
      };
      const audioUrl = `data:audio/wav;base64,${audioBase64}`;
      const xmlUrl = `data:application/xml,${encodeURIComponent(scoreXml)}`;
      return {
        work: {
          id: "mock-work-2",
          project_id: "mock-project-1",
          title: "Performance Work B",
          composer: null,
          created_at: now,
          updated_at: now,
        },
        jobs: [],
        artifacts: [
          item("perf-original-2", "audio_original", audioUrl),
          item("perf-midi-2", "midi_performance", "https://example.com/perf-midi-2.mid"),
          item("perf-rendered-2", "audio_rendered", audioUrl),
          item("perf-score-2", "musicxml_score", xmlUrl),
          item("perf-rendered-score-2", "rendered_score", audioUrl, {
            measure_starts_seconds: [0, 3],
          }),
        ],
      };
    };

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : String(input);
      const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
      const started = performance.now();
      let response: Response;

      if (method === "GET" && url.includes("/api/v1/projects/mock-project-1/works")) {
        const now = new Date().toISOString();
        response = json([
          {
            id: "mock-work-1",
            project_id: "mock-project-1",
            title: "Test Work",
            composer: null,
            created_at: now,
            updated_at: now,
          },
          {
            id: "mock-work-2",
            project_id: "mock-project-1",
            title: "Performance Work B",
            composer: null,
            created_at: now,
            updated_at: now,
          },
        ]);
      } else if (method === "GET" && url.includes("/api/v1/works/mock-work-2")) {
        response = json(workTwoBundle());
      } else if (method === "GET" && url.includes("/api/v1/versions/perf-midi-2/insights")) {
        const span = {
          start_seconds: null,
          end_seconds: null,
          start_beat: null,
          end_beat: null,
          start_measure: null,
          end_measure: null,
        };
        response = json([
          {
            id: "perf-key-2",
            version_id: "perf-midi-2",
            kind: "key",
            claim: "Key: D minor",
            span,
            entity_ids: [],
            evidence: { tonic: "D", mode: "minor" },
            confidence: 0.84,
            provenance: {},
            created_at: new Date().toISOString(),
            created_by: "mock-user-1",
            produced_by_job_id: "perf-analysis-2",
          },
          {
            id: "perf-tempo-2",
            version_id: "perf-midi-2",
            kind: "tempo",
            claim: "Tempo: 97 BPM",
            span,
            entity_ids: [],
            evidence: { bpm: 97 },
            confidence: 0.86,
            provenance: {},
            created_at: new Date().toISOString(),
            created_by: "mock-user-1",
            produced_by_job_id: "perf-analysis-2",
          },
          {
            id: "perf-meter-2",
            version_id: "perf-midi-2",
            kind: "time_signature",
            claim: "Time Signature: 3/4",
            span,
            entity_ids: [],
            evidence: { numerator: 3, denominator: 4 },
            confidence: 0.9,
            provenance: {},
            created_at: new Date().toISOString(),
            created_by: "mock-user-1",
            produced_by_job_id: "perf-analysis-2",
          },
        ]);
      } else {
        response = await originalFetch(input, init);
      }

      fetchSamples.push({
        kind: classify(url),
        method,
        started_ms: started,
        duration_ms: performance.now() - started,
        status: response.status,
      });
      return response;
    };
  };
}

async function browserNow(page: Page): Promise<number> {
  return page.evaluate(() => performance.now());
}

async function fetchLogLength(page: Page): Promise<number> {
  return page.evaluate(() => {
    const target = window as Window & { __workOpenPerfFetches?: FetchSample[] };
    return target.__workOpenPerfFetches?.length ?? 0;
  });
}

async function fetchesSince(page: Page, offset: number): Promise<FetchSample[]> {
  return page.evaluate((start) => {
    const target = window as Window & { __workOpenPerfFetches?: FetchSample[] };
    return (target.__workOpenPerfFetches ?? []).slice(start);
  }, offset);
}

function countFetches(samples: FetchSample[]): Record<FetchKind, number> {
  const counts: Record<FetchKind, number> = {
    work_list: 0,
    work_bundle: 0,
    entities: 0,
    insights: 0,
    score_xml: 0,
    audio: 0,
    other: 0,
  };
  for (const sample of samples) counts[sample.kind] += 1;
  return counts;
}

async function measureOpen(
  page: Page,
  title: string,
  expectedKey: string,
  label: string,
): Promise<OpenSample> {
  const row = page.getByRole("button", { name: new RegExp(`^${title}\\b`) });
  const fetchOffset = await fetchLogLength(page);
  const started = await browserNow(page);

  await row.click();
  await expect(row).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("button", { name: /Playback source:/ })).toBeVisible({ timeout: 10_000 });
  const sourceReady = (await browserNow(page)) - started;

  await expect(page.getByText(expectedKey, { exact: true })).toBeVisible({ timeout: 10_000 });
  const evidenceReady = (await browserNow(page)) - started;
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("tab", { name: "Score" })).toBeVisible({ timeout: 10_000 });
  const workspaceReady = (await browserNow(page)) - started;

  const scoreStarted = await browserNow(page);
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container g.vf-measure").first()).toBeVisible({ timeout: 20_000 });
  const scoreRenderReady = (await browserNow(page)) - scoreStarted;
  await page.getByRole("tab", { name: "Waveform" }).click();

  const fetches = await fetchesSince(page, fetchOffset);
  return {
    label,
    source_ready_ms: sourceReady,
    evidence_ready_ms: evidenceReady,
    workspace_artifacts_ready_ms: workspaceReady,
    score_render_ready_ms: scoreRenderReady,
    fetch_counts: countFetches(fetches),
  };
}

test("reports cold B and warm A saved-Work open latency without absolute CI thresholds", async ({
  page,
}, testInfo) => {
  await page.addInitScript(persistSessionScript(), {
    projectRef: MOCK_PROJECT_REF,
    session: mockSession,
  });
  await page.addInitScript(installPerformanceFixtureScript(), {
    audioBase64: sampleWavOutputBase64,
    scoreXml: performanceScoreXml,
  });

  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await page.reload();

  const workA = page.getByRole("button", { name: /^Test Work\b/ });
  const workB = page.getByRole("button", { name: /^Performance Work B\b/ });
  await expect(workA).toBeVisible({ timeout: 20_000 });
  await expect(workB).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("A minor", { exact: true })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Score" })).toBeVisible({ timeout: 20_000 });

  // Render A once before leaving it. The later A sample therefore includes the
  // current cost of rebuilding a previously visited score after A -> B -> A.
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container g.vf-measure").first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole("tab", { name: "Waveform" }).click();

  const coldB = await measureOpen(page, "Performance Work B", "D minor", "cold_b");
  const warmA = await measureOpen(page, "Test Work", "A minor", "warm_a_after_b");

  // Deterministic cache evidence, not a hosted-run millisecond gate: revisiting
  // A should reuse its stable Work/evidence API data within the five-minute TTL.
  expect(warmA.fetch_counts.work_bundle).toBe(0);
  expect(warmA.fetch_counts.entities).toBe(0);
  expect(warmA.fetch_counts.insights).toBe(0);

  const report = {
    schema_version: 1,
    scenario: "saved_work_a_b_a",
    clock: "browser_performance_now",
    thresholds_enforced: false,
    samples: [coldB, warmA],
  };
  await testInfo.attach("work-open-performance.json", {
    body: Buffer.from(`${JSON.stringify(report, null, 2)}\n`),
    contentType: "application/json",
  });
});

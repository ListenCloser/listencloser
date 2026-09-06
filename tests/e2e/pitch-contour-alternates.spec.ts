import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

function installPitchAlternatesHarness() {
  const originalFetch = window.fetch.bind(window);
  const jobs = new Map<string, string>();
  const available = new Set<string>();
  let jobCounter = 0;
  const harnessWindow = window as typeof window & { __pitchRequests?: string[] };
  harnessWindow.__pitchRequests = [];

  const jsonResponse = (body: unknown) => new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

  const pitchData = (engine: string) => ({
    schema_version: 1,
    representation_type: "pitch_contour",
    status: "experimental",
    source_audio_version_id: "mock-version-1",
    requested_engine: engine,
    engine: engine === "pesto"
      ? {
          name: "pesto",
          version: "2.0.1",
          method: "PESTO ALWA",
          model: "mir-1k_g7",
          model_sha256: "pesto-sha",
          license: "LGPL-3.0",
        }
      : engine === "torchcrepe"
        ? {
            name: "torchcrepe",
            version: "0.0.24",
            method: "CREPE tiny + Viterbi",
            model: "tiny.pth",
            model_sha256: "crepe-sha",
            license: "MIT",
          }
        : {
            name: "librosa",
            version: "0.11.0",
            method: "pyin",
            model: "algorithmic pYIN; no learned checkpoint",
            license: "ISC",
          },
    preprocessing: {
      sample_rate_hz: 22050,
      hop_seconds: 0.01,
      fmin_hz: 50,
      fmax_hz: 1600,
      pitch_cents_reference: "absolute MIDI cents; A4=440 Hz=6900 cents",
    },
    frames: [
      { frame: 0, time_seconds: 0, pitch_hz: 220, pitch_cents: 5700, voiced: true, voiced_probability: engine === "pyin" ? 0.91 : null },
      { frame: 1, time_seconds: 1, pitch_hz: 233.08, pitch_cents: 5800, voiced: true, voiced_probability: engine === "pyin" ? 0.92 : null },
      { frame: 2, time_seconds: 2, pitch_hz: 246.94, pitch_cents: 5900, voiced: true, voiced_probability: engine === "pyin" ? 0.93 : null },
    ],
  });

  window.fetch = async (input, init) => {
    const requestUrl = typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
    const url = new URL(requestUrl, window.location.href);
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();

    if (method === "POST" && url.pathname === "/api/v1/workflows/create") {
      const rawBody = input instanceof Request
        ? await input.clone().text()
        : typeof init?.body === "string"
          ? init.body
          : "";
      const body = rawBody
        ? JSON.parse(rawBody) as { action?: string; parameters?: { pitch_engine?: string } }
        : {};
      if (body.action === "pitch_contour") {
        const engine = body.parameters?.pitch_engine ?? "pyin";
        jobCounter += 1;
        const jobId = `mock-pitch-job-${engine}-${jobCounter}`;
        jobs.set(jobId, engine);
        harnessWindow.__pitchRequests?.push(engine);
        const now = new Date().toISOString();
        return jsonResponse({
          workflow: {
            id: `mock-pitch-workflow-${engine}-${jobCounter}`,
            project_id: "mock-project-1",
            kind: "create",
            target_version_id: "mock-version-1",
            parameters: { action: "pitch_contour", pitch_engine: engine },
            created_at: now,
          },
          job: {
            id: jobId,
            workflow_id: `mock-pitch-workflow-${engine}-${jobCounter}`,
            capability: {
              name: "pitch_contour",
              version: "1.0",
              accepted_input_kinds: [],
              produces_output_kinds: [],
              parameters: {},
              failure_modes: [],
            },
            lifecycle: {
              current: "queued",
              progress: 0,
              message: "Queued pitch contour",
              stages: [],
              retry_count: 0,
              max_retries: 3,
              lease_expires_at: null,
              started_at: null,
              completed_at: null,
            },
            input_version_ids: ["mock-version-1"],
            output_version_ids: [],
            parameters: { pitch_engine: engine },
            cache_key: null,
            error: null,
            error_details: {},
            provenance: {},
            created_at: now,
            created_by: "mock-user-1",
          },
        });
      }
    }

    if (method === "GET" && url.pathname.startsWith("/api/v1/jobs/mock-pitch-job-")) {
      const jobId = url.pathname.split("/").at(-1) ?? "";
      const engine = jobs.get(jobId);
      if (engine) {
        available.add(engine);
        return jsonResponse({
          id: jobId,
          workflow_id: `mock-pitch-workflow-${engine}`,
          capability: "pitch_contour",
          stage: "succeeded",
          progress: 1,
          message: "Pitch contour complete",
          error: null,
          input_version_ids: ["mock-version-1"],
          output_version_ids: [`mock-pitch-version-${engine}`],
        });
      }
    }

    const response = await originalFetch(input, init);
    if (method === "GET" && url.pathname === "/api/v1/works/mock-work-1" && available.size > 0) {
      const body = await response.clone().json() as {
        artifacts: Array<Record<string, unknown>>;
        [key: string]: unknown;
      };
      const now = new Date().toISOString();
      const pitchArtifacts = [...available].map((engine) => {
        const payload = pitchData(engine);
        const version = {
          id: `mock-pitch-version-${engine}`,
          artifact_id: `artifact-mock-pitch-${engine}`,
          storage_bucket: "artifacts",
          storage_key: `mock/pitch-${engine}.json`,
          parent_version_id: "mock-version-1",
          lineage: ["mock-version-1"],
          byte_size: 512,
          sha256: null,
          label: "Pitch contour · Experimental",
          metadata: {
            representation_type: "pitch_contour",
            status: "experimental",
            source_audio_version_id: "mock-version-1",
            requested_engine: engine,
            engine: payload.engine,
          },
          created_at: now,
          created_by: "mock-user-1",
          produced_by_job_id: `mock-pitch-job-${engine}`,
        };
        return {
          artifact: {
            id: `artifact-mock-pitch-${engine}`,
            work_id: "mock-work-1",
            kind: "analysis_report",
            mime_type: "application/json",
            created_at: now,
          },
          versions: [version],
          latest_version: version,
          signed_url: `data:application/json,${encodeURIComponent(JSON.stringify(payload))}`,
        };
      });
      return jsonResponse({
        ...body,
        artifacts: [...body.artifacts, ...pitchArtifacts],
      });
    }

    return response;
  };
}

test("Pitch Contour generates an alternate once and reselects existing interpretations cheaply", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.addInitScript(installPitchAlternatesHarness);
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await page.reload();

  await page.getByRole("button", { name: "+ Add analysis" }).first().click();
  const chooser = page.getByRole("region", { name: "Add analysis" });
  const pitchChoice = chooser.getByText("Pitch Contour", { exact: true }).locator("xpath=../../..");
  await pitchChoice.getByRole("button", { name: "Add" }).click();

  const lane = page.getByTestId("pitch-contour-lane");
  await expect(lane).toBeVisible({ timeout: 10_000 });
  await lane.getByText("Details", { exact: true }).click();
  await expect(lane.getByText("Interpretation: pYIN", { exact: true })).toBeVisible();

  await lane.getByRole("button", { name: "Generate PESTO" }).click();
  await expect(lane.getByText("Interpretation: PESTO", { exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(lane.getByText(/Voicing confidence is PESTO-specific/)).toBeVisible();

  await lane.getByRole("button", { name: "Show pYIN" }).click();
  await expect(lane.getByText("Interpretation: pYIN", { exact: true })).toBeVisible();

  const requests = await page.evaluate(() => (
    (window as typeof window & { __pitchRequests?: string[] }).__pitchRequests ?? []
  ));
  expect(requests).toEqual(["pyin", "pesto"]);
});

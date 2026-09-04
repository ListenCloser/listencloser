import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

function installPitchContourHarness() {
  const originalFetch = window.fetch.bind(window);
  let pitchRequested = false;
  let pitchReady = false;

  const jsonResponse = (body: unknown) => new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

  const pitchData = {
    schema_version: 1,
    representation_type: "pitch_contour",
    status: "experimental",
    source_audio_version_id: "mock-version-1",
    engine: {
      name: "librosa",
      version: "0.11.0",
      method: "pyin",
      model: null,
      license: "ISC",
    },
    preprocessing: {
      sample_rate_hz: 22050,
      hop_seconds: 0.01,
      fmin_hz: 50,
      fmax_hz: 1600,
      pitch_cents_reference: "absolute cents from MIDI C-1 = 0",
    },
    frames: [
      { frame: 0, time_seconds: 0, pitch_hz: 220, pitch_cents: 5700, voiced: true, voiced_probability: 0.91 },
      { frame: 1, time_seconds: 1, pitch_hz: 233.08, pitch_cents: 5800, voiced: true, voiced_probability: 0.92 },
      { frame: 2, time_seconds: 2, pitch_hz: 246.94, pitch_cents: 5900, voiced: true, voiced_probability: 0.93 },
      { frame: 3, time_seconds: 3, pitch_hz: 261.63, pitch_cents: 6000, voiced: true, voiced_probability: 0.94 },
    ],
  };
  const signedPitchUrl = `data:application/json,${encodeURIComponent(JSON.stringify(pitchData))}`;

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
      const body = rawBody ? JSON.parse(rawBody) as { action?: string } : {};
      if (body.action === "pitch_contour") {
        pitchRequested = true;
        const now = new Date().toISOString();
        return jsonResponse({
          workflow: {
            id: "mock-pitch-workflow",
            project_id: "mock-project-1",
            kind: "create",
            target_version_id: "mock-version-1",
            parameters: { action: "pitch_contour" },
            created_at: now,
          },
          job: {
            id: "mock-pitch-job",
            workflow_id: "mock-pitch-workflow",
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
            parameters: {},
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

    if (method === "GET" && url.pathname === "/api/v1/jobs/mock-pitch-job" && pitchRequested) {
      pitchReady = true;
      return jsonResponse({
        id: "mock-pitch-job",
        workflow_id: "mock-pitch-workflow",
        capability: "pitch_contour",
        stage: "succeeded",
        progress: 1,
        message: "Pitch contour complete",
        error: null,
        input_version_ids: ["mock-version-1"],
        output_version_ids: ["mock-pitch-version"],
      });
    }

    const response = await originalFetch(input, init);
    if (method === "GET" && url.pathname === "/api/v1/works/mock-work-1" && pitchReady) {
      const body = await response.clone().json() as {
        artifacts: Array<Record<string, unknown>>;
        [key: string]: unknown;
      };
      const now = new Date().toISOString();
      const version = {
        id: "mock-pitch-version",
        artifact_id: "artifact-mock-pitch-version",
        storage_bucket: "artifacts",
        storage_key: "mock/mock-pitch-version.json",
        parent_version_id: "mock-version-1",
        lineage: ["mock-version-1"],
        byte_size: 512,
        sha256: null,
        label: "Pitch contour",
        metadata: { representation_type: "pitch_contour", status: "experimental" },
        created_at: now,
        created_by: "mock-user-1",
        produced_by_job_id: "mock-pitch-job",
      };
      return jsonResponse({
        ...body,
        artifacts: [
          ...body.artifacts,
          {
            artifact: {
              id: "artifact-mock-pitch-version",
              work_id: "mock-work-1",
              kind: "analysis_report",
              mime_type: "application/json",
              created_at: now,
            },
            versions: [version],
            latest_version: version,
            signed_url: signedPitchUrl,
          },
        ],
      });
    }

    return response;
  };
}

test("Pitch contour stays an optional synchronized result instead of a fifth primary representation", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.addInitScript(installPitchContourHarness);
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await page.reload();

  const representationTabs = page.getByRole("tablist", { name: "Music representation" });
  await expect(representationTabs.getByRole("tab")).toHaveCount(4, { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();

  const processing = page.locator("details.library-import-settings");
  await processing.locator("summary").click();
  const pitch = page.getByTestId("pitch-contour-processing");
  await expect(pitch).toContainText("Pitch contour");
  await expect(pitch).toContainText("Not added");

  await pitch.getByRole("button", { name: "Add" }).click();
  await expect(pitch.getByRole("button", { name: "Processing pitch contour…" })).toBeDisabled();
  await expect(pitch).toContainText("Ready", { timeout: 10_000 });
  await expect(page.getByTestId("pitch-contour-lane")).not.toBeVisible();

  await pitch.getByRole("button", { name: "Open" }).click();
  const lane = page.getByTestId("pitch-contour-lane");
  await expect(lane).toBeVisible();
  await expect(lane.getByTestId("pitch-contour-plot")).toBeVisible();
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();

  await representationTabs.getByRole("tab", { name: "Score" }).click();
  await expect(lane).toBeVisible();
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();

  const position = page.getByRole("slider", { name: "Playback position" });
  const beforeSeek = Number(await position.inputValue());
  await lane.getByTestId("pitch-contour-plot").click();
  await expect.poll(async () => Number(await position.inputValue())).toBeGreaterThan(beforeSeek);

  await lane.getByRole("button", { name: "Hide" }).click();
  await expect(lane).not.toBeVisible();
  await pitch.getByRole("button", { name: "Open" }).click();
  await expect(page.getByTestId("pitch-contour-lane")).toBeVisible();
  await expect(representationTabs.getByRole("tab")).toHaveCount(4);

  await page.setViewportSize({ width: 390, height: 844 });
  const narrowLane = page.getByTestId("pitch-contour-lane");
  await expect(narrowLane).toBeVisible();
  const laneBox = await narrowLane.boundingBox();
  expect(laneBox).not.toBeNull();
  expect(laneBox!.x).toBeGreaterThanOrEqual(0);
  expect(laneBox!.x + laneBox!.width).toBeLessThanOrEqual(390);
  await expect(representationTabs.getByRole("tab")).toHaveCount(4);
});

import { expect, test, type Locator, type Page } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

function installLayerFetchFixture({ fail }: { fail: boolean }) {
  const layerJobId = "mock-separate-job";
  const layerWorkflowId = "mock-separate-workflow";
  const layerRoles = ["vocals", "drums", "bass", "other"] as const;
  const nativeFetch = window.fetch.bind(window);
  let separationRequested = false;

  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

  const workflowJob = () => ({
    workflow: {
      id: layerWorkflowId,
      project_id: "mock-project-1",
      kind: "create",
      target_version_id: null,
      parameters: { action: "separate" },
      created_at: new Date().toISOString(),
    },
    job: {
      id: layerJobId,
      workflow_id: layerWorkflowId,
      capability: {
        name: "separate",
        version: "1.0",
        accepted_input_kinds: [],
        produces_output_kinds: [],
        parameters: {},
        failure_modes: [],
      },
      lifecycle: {
        current: "running",
        progress: 0.5,
        message: "Separating layers…",
        stages: [],
        retry_count: 0,
        max_retries: 3,
        lease_expires_at: null,
        started_at: new Date().toISOString(),
        completed_at: null,
      },
      input_version_ids: ["mock-version-1"],
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

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url, window.location.origin);

    if (url.pathname === "/api/v1/workflows/create" && request.method === "POST") {
      const body = await request.clone().json() as { action?: string };
      if (body.action === "separate") {
        separationRequested = true;
        return json(workflowJob());
      }
    }

    if (url.pathname === `/api/v1/jobs/${layerJobId}` && request.method === "GET") {
      return json({
        id: layerJobId,
        workflow_id: layerWorkflowId,
        capability: "separate",
        stage: fail ? "failed" : "succeeded",
        progress: 1,
        message: fail ? "Layer separation failed in the browser fixture." : "Layers ready",
        error: fail ? "Mock layer separation failure" : null,
        input_version_ids: ["mock-version-1"],
        output_version_ids: fail ? [] : layerRoles.map((role) => `mock-stem-${role}`),
      });
    }

    if (
      separationRequested
      && !fail
      && url.pathname === "/api/v1/works/mock-work-1"
      && request.method === "GET"
    ) {
      const response = await nativeFetch(input, init);
      const bundle = await response.clone().json() as {
        artifacts: Array<Record<string, unknown>>;
      };
      const now = new Date().toISOString();
      const stems = layerRoles.map((role) => {
        const id = `mock-stem-${role}`;
        const version = {
          id,
          artifact_id: `artifact-${id}`,
          storage_bucket: "artifacts",
          storage_key: `mock/${id}.wav`,
          parent_version_id: "mock-version-1",
          lineage: [],
          byte_size: 100,
          sha256: null,
          label: `${role}.wav`,
          metadata: { stem_role: role },
          created_at: now,
          created_by: "mock-user-1",
          produced_by_job_id: layerJobId,
        };
        return {
          artifact: {
            id: `artifact-${id}`,
            work_id: "mock-work-1",
            kind: "stems",
            mime_type: "audio/wav",
            created_at: now,
          },
          versions: [version],
          latest_version: version,
          signed_url: "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=",
        };
      });
      return json({ ...bundle, artifacts: [...stems, ...bundle.artifacts] });
    }

    return nativeFetch(input, init);
  };
}

async function openOrdinaryWork(page: Page, filename: string, failSeparation = false) {
  await page.addInitScript(persistSessionScript(), {
    projectRef: MOCK_PROJECT_REF,
    session: mockSession,
  });
  await page.addInitScript(installLayerFetchFixture, { fail: failSeparation });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await page.reload();

  const fileInput = page.locator("#audio-import-input");
  await expect(fileInput).toHaveCount(1, { timeout: 20_000 });
  await fileInput.setInputFiles({
    name: filename,
    mimeType: "audio/mp4",
    buffer: Buffer.from("mock layer isolation payload"),
  });

  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("tab", { name: "Score" })).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByRole("button", { name: "Playback source: Original", exact: true }),
  ).toBeVisible();

  const processing = page.locator("summary").filter({ hasText: /^Processing$/ });
  await processing.click();
  const layers = page.getByTestId("experimental-layers");
  await expect(layers).toBeVisible();
  await expect(layers).toContainText("Layers");
  await expect(layers).toContainText("Experimental");
  return layers;
}

function layerRow(layers: Locator, label: string) {
  return layers.getByText(label, { exact: true }).locator("..");
}

test("Layers stays in Processing and exposes an explicit position-preserving playback-source lifecycle", async ({ page }) => {
  const layers = await openOrdinaryWork(page, "layers-success.m4a");

  await expect(layers.getByRole("button", { name: "Separate layers", exact: true })).toBeVisible();
  await layers.getByRole("button", { name: "Separate layers", exact: true }).click();

  await expect(layers.getByText("Vocals", { exact: true })).toBeVisible({ timeout: 10_000 });
  for (const label of ["Original", "Vocals", "Drums", "Bass", "Other"]) {
    await expect(layers.getByText(label, { exact: true })).toBeVisible();
  }

  // Generating Layers never changes the active source, and ordinary Work views
  // remain available after the optional job completes.
  await expect(
    page.getByRole("button", { name: "Playback source: Original", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();

  const position = page.getByRole("slider", { name: "Playback position" });
  await position.focus();
  await position.press("ArrowRight");
  await position.press("ArrowRight");
  const positionBeforeSwitch = await position.inputValue();

  for (const label of ["Vocals", "Drums", "Bass", "Other"]) {
    await layerRow(layers, label).getByRole("button", { name: "Hear", exact: true }).click();
    await expect(
      page.getByRole("button", { name: `Playback source: ${label}`, exact: true }),
    ).toBeVisible();
    await expect(position).toHaveValue(positionBeforeSwitch);
  }

  await layerRow(layers, "Original").getByRole("button", { name: "Hear", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Playback source: Original", exact: true }),
  ).toBeVisible();
  await expect(position).toHaveValue(positionBeforeSwitch);
});

test("failed Layers work stays local and leaves Original plus ordinary Work views usable", async ({ page }) => {
  const layers = await openOrdinaryWork(page, "layers-failure.m4a", true);

  await layers.getByRole("button", { name: "Separate layers", exact: true }).click();
  await expect(layers.getByRole("alert")).toContainText("Original remains available.", {
    timeout: 10_000,
  });
  await expect(layers.getByRole("button", { name: "Retry separate layers", exact: true })).toBeVisible();

  for (const label of ["Vocals", "Drums", "Bass", "Other"]) {
    await expect(layers.getByText(label, { exact: true })).toHaveCount(0);
  }
  await expect(
    page.getByRole("button", { name: "Playback source: Original", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();
});

import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

type WorkBundleLike = {
  jobs: Array<{ lifecycle: Record<string, unknown>; [key: string]: unknown }>;
  artifacts: Array<{ artifact: { kind?: string; [key: string]: unknown }; [key: string]: unknown }>;
  [key: string]: unknown;
};

function installPersistentCancellationHarness() {
  const originalFetch = window.fetch.bind(window);
  const lastJobKey = "listencloser-test-last-understand-job";
  const cancelledKey = "listencloser-test-understand-cancelled";

  const jsonResponse = (response: Response, body: unknown) => {
    const headers = new Headers(response.headers);
    headers.set("content-type", "application/json");
    headers.delete("content-length");
    return new Response(JSON.stringify(body), {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  };

  window.fetch = async (input, init) => {
    const requestUrl = typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
    const url = new URL(requestUrl, window.location.href);
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    const response = await originalFetch(input, init);

    if (method === "POST" && url.pathname === "/api/v1/jobs/mock-job-1/cancel" && response.ok) {
      sessionStorage.setItem(cancelledKey, "true");
      return response;
    }

    if (method !== "GET" || url.pathname !== "/api/v1/works/mock-work-1") return response;

    const body = await response.clone().json() as WorkBundleLike;
    if (body.jobs[0]) {
      sessionStorage.setItem(lastJobKey, JSON.stringify(body.jobs[0]));
    }
    if (sessionStorage.getItem(cancelledKey) !== "true") return response;

    const storedJob = sessionStorage.getItem(lastJobKey);
    if (!storedJob) return response;
    const lastJob = JSON.parse(storedJob) as WorkBundleLike["jobs"][number];
    const cancelledJob = {
      ...lastJob,
      lifecycle: {
        ...lastJob.lifecycle,
        current: "cancelled",
        message: "cancelled by user",
        completed_at: new Date().toISOString(),
      },
      error: null,
    };
    const originalArtifacts = body.artifacts.filter((item) => item.artifact.kind === "audio_original");

    return jsonResponse(response, {
      ...body,
      jobs: [cancelledJob],
      artifacts: originalArtifacts.length > 0 ? originalArtifacts : body.artifacts,
    });
  };
}

test("cancelling understanding remains a successful stop after reload", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.addInitScript(installPersistentCancellationHarness);
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await page.reload();

  const importButton = page.getByRole("complementary").getByRole("button", { name: "Import audio" });
  await expect(importButton).toBeVisible({ timeout: 20_000 });
  await expect(importButton).toBeEnabled({ timeout: 10_000 });
  await importButton.click();
  await page.getByRole("menuitem", { name: /Upload recording/ }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "cancel-fixture.m4a",
    mimeType: "audio/mp4",
    buffer: Buffer.from("mock cancellation m4a payload"),
  });

  const processingNotice = page.locator(".workspace-processing-notice");
  await expect(page.getByText("Ready to listen.", { exact: true })).toBeVisible({ timeout: 5_000 });
  await expect(processingNotice).toBeVisible();
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();

  await processingNotice.getByRole("button", { name: "Cancel", exact: true }).click();

  // The backend persists `cancelled` as a terminal Job stage. A deliberate
  // cancellation must stop processing narration without being translated into
  // the failure + Retry UX, while the already-durable source remains usable.
  await expect(processingNotice).not.toBeVisible({ timeout: 5_000 });
  await expect(page.getByText("Couldn’t finish understanding this recording.", { exact: true })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Retry", exact: true })).not.toBeVisible();
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();

  // The page-local harness keeps returning the same persisted cancelled Job
  // after navigation. Reload therefore proves this is durable interpretation,
  // not a transient local state that only looks correct immediately after the
  // Cancel click.
  await page.reload();
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();
  await expect(page.locator(".workspace-processing-notice")).not.toBeVisible();
  await expect(page.getByText("Couldn’t finish understanding this recording.", { exact: true })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Retry", exact: true })).not.toBeVisible();
});

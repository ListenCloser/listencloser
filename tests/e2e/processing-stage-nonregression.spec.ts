import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

const PROGRESS_KEY = "listencloser-test-understand-progress";
const JOB_KEY = "listencloser-test-understand-job";

type JobLike = {
  lifecycle: Record<string, unknown>;
  [key: string]: unknown;
};

type WorkBundleLike = {
  jobs: JobLike[];
  artifacts: Array<{ artifact: { kind?: string; [key: string]: unknown }; [key: string]: unknown }>;
  [key: string]: unknown;
};

function installDurableProgressHarness() {
  const originalFetch = window.fetch.bind(window);

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

    if (method === "POST" && url.pathname === "/api/v1/workflows/understand" && response.ok) {
      const body = await response.clone().json() as { job?: JobLike };
      if (body.job) {
        sessionStorage.setItem(JOB_KEY, JSON.stringify(body.job));
        sessionStorage.setItem(PROGRESS_KEY, "0.15");
      }
      return response;
    }

    if (method !== "GET" || url.pathname !== "/api/v1/works/mock-work-1") return response;

    const storedJob = sessionStorage.getItem(JOB_KEY);
    if (!storedJob) return response;

    const body = await response.clone().json() as WorkBundleLike;
    const progress = Number(sessionStorage.getItem(PROGRESS_KEY) ?? "0.15");
    const template = JSON.parse(storedJob) as JobLike;
    const runningJob: JobLike = {
      ...template,
      lifecycle: {
        ...template.lifecycle,
        current: "running",
        progress,
        message: "Understanding audio...",
        completed_at: null,
      },
      error: null,
    };
    const originalArtifacts = body.artifacts.filter((item) => item.artifact.kind === "audio_original");

    return jsonResponse(response, {
      ...body,
      jobs: [runningJob],
      artifacts: originalArtifacts.length > 0 ? originalArtifacts : body.artifacts,
    });
  };
}

async function setDurableProgress(page: import("@playwright/test").Page, progress: number) {
  await page.evaluate(({ key, value }) => {
    sessionStorage.setItem(key, String(value));
  }, { key: PROGRESS_KEY, value: progress });
}

test("processing stage never restarts across polling or page remount", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.addInitScript(installDurableProgressHarness);
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
    name: "stage-progression.m4a",
    mimeType: "audio/mp4",
    buffer: Buffer.from("mock stage progression payload"),
  });

  const notice = page.locator(".workspace-processing-notice");
  await expect(notice).toContainText("Preparing your recording…", { timeout: 5_000 });
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

  // Advance the durable Job through the same progress bands emitted by the
  // composite understand workflow. WorkspaceSession should merely project that
  // source-of-truth state on its normal polling cadence.
  await setDurableProgress(page, 0.45);
  await expect(notice).toContainText("Transcribing notes…", { timeout: 5_000 });
  await expect(notice).not.toContainText("Preparing your recording…");

  await setDurableProgress(page, 0.8);
  await expect(notice).toContainText("Analyzing the music…", { timeout: 5_000 });
  await expect(notice).not.toContainText("Preparing your recording…");
  await expect(notice).not.toContainText("Transcribing notes…");

  // sessionStorage models the persisted server value across a client remount.
  // Reloading while analysis is at 80% must resume from that durable stage,
  // never flash back to the initial/transcription stages because local state was
  // recreated.
  await page.reload();
  const remountedNotice = page.locator(".workspace-processing-notice");
  await expect(remountedNotice).toContainText("Analyzing the music…", { timeout: 10_000 });
  await expect(remountedNotice).not.toContainText("Preparing your recording…");
  await expect(remountedNotice).not.toContainText("Transcribing notes…");
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

  await setDurableProgress(page, 0.95);
  await expect(remountedNotice).toContainText("Building the score…", { timeout: 5_000 });
  await expect(remountedNotice).not.toContainText("Analyzing the music…");
  await expect(remountedNotice).not.toContainText("Transcribing notes…");
  await expect(remountedNotice).not.toContainText("Preparing your recording…");
});

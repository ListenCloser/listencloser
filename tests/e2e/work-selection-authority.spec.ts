import { expect, test, type Page } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

type WorkAuthorityHarness = {
  holdWorkId: string | null;
  heldWorkId: string | null;
  releaseHeld: (() => void) | null;
  staleAudioAssignments: string[];
  processingWorkId: string | null;
};

declare global {
  interface Window {
    __lcWorkAuthority?: WorkAuthorityHarness;
  }
}

const HOLD_KEY = "lc-e2e-hold-work";
const STALE_SOURCE_KEY = "lc-e2e-stale-work-source";

function installWorkAuthorityHarness({ holdKey, staleSourceKey }: { holdKey: string; staleSourceKey: string }) {
  const originalFetch = window.fetch.bind(window);
  const originalMediaLoad = HTMLMediaElement.prototype.load;
  const harness: WorkAuthorityHarness = {
    holdWorkId: window.sessionStorage.getItem(holdKey),
    heldWorkId: null,
    releaseHeld: null,
    staleAudioAssignments: [],
    processingWorkId: null,
  };
  window.__lcWorkAuthority = harness;

  const selectedWorkId = () => {
    const selected = document.querySelector<HTMLButtonElement>(".library-work-btn[aria-current='true']");
    const title = selected?.querySelector(".library-work-title")?.textContent?.trim();
    if (title === "Work A") return "mock-work-a";
    if (title === "Work B") return "mock-work-b";
    return null;
  };

  HTMLMediaElement.prototype.load = function load() {
    const src = this.getAttribute("src") ?? "";
    const sourceWorkId = src.includes("#mock-work-a")
      ? "mock-work-a"
      : src.includes("#mock-work-b")
        ? "mock-work-b"
        : null;
    const selected = selectedWorkId();
    if (sourceWorkId && selected && sourceWorkId !== selected) {
      const observation = `${selected} received ${sourceWorkId}`;
      harness.staleAudioAssignments.push(observation);
      window.sessionStorage.setItem(staleSourceKey, observation);
    }
    return originalMediaLoad.call(this);
  };

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
    if (method !== "GET") return response;

    if (/^\/api\/v1\/projects\/[^/]+\/works$/.test(url.pathname)) {
      const baseWorks = await response.clone().json() as Array<Record<string, unknown>>;
      const base = baseWorks[0] ?? {};
      const now = new Date().toISOString();
      return jsonResponse(response, [
        {
          ...base,
          id: "mock-work-a",
          project_id: "mock-project-1",
          title: "Work A",
          composer: null,
          created_at: base.created_at ?? now,
          updated_at: base.updated_at ?? now,
        },
        {
          ...base,
          id: "mock-work-b",
          project_id: "mock-project-1",
          title: "Work B",
          composer: null,
          created_at: base.created_at ?? now,
          updated_at: base.updated_at ?? now,
        },
      ]);
    }

    const bundleMatch = url.pathname.match(/^\/api\/v1\/works\/(mock-work-[ab])$/);
    if (!bundleMatch) return response;

    const workId = bundleMatch[1];
    const body = await response.clone().json() as {
      work: Record<string, unknown>;
      artifacts: Array<{
        artifact: Record<string, unknown>;
        versions: Array<Record<string, unknown>>;
        latest_version: Record<string, unknown> | null;
        signed_url: string | null;
      }>;
    };
    const original = body.artifacts.find((item) => item.artifact.kind === "audio_original");
    if (!original?.latest_version || !original.signed_url) return response;

    const suffix = workId.endsWith("a") ? "a" : "b";
    const artifactId = `mock-artifact-${suffix}`;
    const versionId = `mock-version-${suffix}`;
    const now = new Date().toISOString();
    const latestVersion = {
      ...original.latest_version,
      id: versionId,
      artifact_id: artifactId,
      storage_key: `test/${versionId}.wav`,
    };
    const processingJob = {
      id: `mock-job-${suffix}`,
      workflow_id: `mock-workflow-${suffix}`,
      capability: {
        name: "understand",
        version: "1.0",
        accepted_input_kinds: [],
        produces_output_kinds: [],
        parameters: {},
        failure_modes: [],
      },
      lifecycle: {
        current: "running",
        progress: 0.5,
        message: "Understanding audio...",
        stages: [],
        retry_count: 0,
        max_retries: 3,
        lease_expires_at: null,
        started_at: now,
        completed_at: null,
      },
      input_version_ids: [versionId],
      output_version_ids: [],
      parameters: {},
      cache_key: null,
      error: null,
      error_details: {},
      provenance: {},
      created_at: now,
      created_by: null,
    };
    const rewritten = {
      work: {
        ...body.work,
        id: workId,
        project_id: "mock-project-1",
        title: suffix === "a" ? "Work A" : "Work B",
      },
      jobs: harness.processingWorkId === workId ? [processingJob] : [],
      artifacts: [{
        ...original,
        artifact: {
          ...original.artifact,
          id: artifactId,
          work_id: workId,
        },
        versions: [latestVersion],
        latest_version: latestVersion,
        signed_url: `${original.signed_url.split("#")[0]}#${workId}`,
      }],
    };

    if (harness.holdWorkId === workId) {
      await new Promise<void>((resolve) => {
        harness.heldWorkId = workId;
        harness.releaseHeld = () => {
          harness.holdWorkId = null;
          harness.heldWorkId = null;
          harness.releaseHeld = null;
          window.sessionStorage.removeItem(holdKey);
          resolve();
        };
      });
    }

    return jsonResponse(response, rewritten);
  };
}

function workButton(page: Page, title: "Work A" | "Work B") {
  return page.locator(".library-work-btn").filter({ hasText: title });
}

async function clickWork(page: Page, title: "Work A" | "Work B") {
  await page.evaluate((nextTitle) => {
    const button = [...document.querySelectorAll<HTMLButtonElement>(".library-work-btn")]
      .find((candidate) => candidate.querySelector(".library-work-title")?.textContent?.trim() === nextTitle);
    if (!button) throw new Error(`Missing ${nextTitle} button`);
    button.click();
  }, title);
}

async function clickWorkAndReleaseHeld(page: Page, title: "Work A" | "Work B") {
  await page.evaluate((nextTitle) => {
    const harness = window.__lcWorkAuthority;
    if (!harness?.releaseHeld) throw new Error("No held Work response to release");
    const button = [...document.querySelectorAll<HTMLButtonElement>(".library-work-btn")]
      .find((candidate) => candidate.querySelector(".library-work-title")?.textContent?.trim() === nextTitle);
    if (!button) throw new Error(`Missing ${nextTitle} button`);

    // Keep selection and stale-response completion in one browser task. React
    // commits the discrete selection before passive effects start the next
    // Work load, which reproduces the authority gap that request sequencing
    // alone cannot cover.
    button.click();
    harness.releaseHeld();
  }, title);
}

async function expectAudioFor(page: Page, workId: "mock-work-a" | "mock-work-b") {
  await expect.poll(async () => page.locator("audio").getAttribute("src")).toContain(`#${workId}`);
}

async function expectNoStaleSource(page: Page) {
  await expect.poll(async () => page.evaluate((staleSourceKey) => window.sessionStorage.getItem(staleSourceKey), STALE_SOURCE_KEY)).toBeNull();
  await expect.poll(async () => page.evaluate(() => window.__lcWorkAuthority?.staleAudioAssignments ?? [])).toEqual([]);
}

async function bootWorkspace(page: Page, initialHold: "mock-work-a" | null) {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.addInitScript(installWorkAuthorityHarness, { holdKey: HOLD_KEY, staleSourceKey: STALE_SOURCE_KEY });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await page.evaluate(({ holdKey, staleSourceKey, workId }) => {
    window.sessionStorage.removeItem(staleSourceKey);
    if (workId) window.sessionStorage.setItem(holdKey, workId);
    else window.sessionStorage.removeItem(holdKey);
  }, { holdKey: HOLD_KEY, staleSourceKey: STALE_SOURCE_KEY, workId: initialHold });
  await page.reload();
  await expect(workButton(page, "Work A")).toBeVisible({ timeout: 20_000 });
  await expect(workButton(page, "Work B")).toBeVisible({ timeout: 20_000 });
}

test("Work B stays authoritative when an older Work A response resolves in the render-to-effect gap", async ({ page }) => {
  await bootWorkspace(page, "mock-work-a");
  await expect(workButton(page, "Work A")).toHaveAttribute("aria-current", "true");
  await page.waitForFunction(() => window.__lcWorkAuthority?.heldWorkId === "mock-work-a");

  await clickWorkAndReleaseHeld(page, "Work B");

  await expect(workButton(page, "Work B")).toHaveAttribute("aria-current", "true");
  await expectAudioFor(page, "mock-work-b");
  await expectNoStaleSource(page);

  // Reload is the persistence boundary: a new client session may choose its
  // default Work again, but selected row and audible source must still agree.
  await page.reload();
  await expect(workButton(page, "Work A")).toHaveAttribute("aria-current", "true");
  await expectAudioFor(page, "mock-work-a");
  await expectNoStaleSource(page);
});

test("Work A stays authoritative when an older Work B response resolves after switching back", async ({ page }) => {
  await bootWorkspace(page, null);
  await expect(workButton(page, "Work A")).toHaveAttribute("aria-current", "true");
  await expectAudioFor(page, "mock-work-a");

  await page.evaluate((holdKey) => {
    const harness = window.__lcWorkAuthority;
    if (!harness) throw new Error("Missing Work authority harness");
    harness.holdWorkId = "mock-work-b";
    window.sessionStorage.setItem(holdKey, "mock-work-b");
  }, HOLD_KEY);
  await clickWork(page, "Work B");
  await expect(workButton(page, "Work B")).toHaveAttribute("aria-current", "true");
  await page.waitForFunction(() => window.__lcWorkAuthority?.heldWorkId === "mock-work-b");

  await clickWorkAndReleaseHeld(page, "Work A");

  await expect(workButton(page, "Work A")).toHaveAttribute("aria-current", "true");
  await expectAudioFor(page, "mock-work-a");
  await expectNoStaleSource(page);
});

test("processing status follows Work B when switching away and returning", async ({ page }) => {
  await bootWorkspace(page, null);
  await expect(workButton(page, "Work A")).toHaveAttribute("aria-current", "true");
  await expectAudioFor(page, "mock-work-a");

  await page.evaluate(() => {
    const harness = window.__lcWorkAuthority;
    if (!harness) throw new Error("Missing Work authority harness");
    harness.processingWorkId = "mock-work-b";
  });

  const notice = page.locator(".workspace-processing-notice");
  await clickWork(page, "Work B");
  await expect(workButton(page, "Work B")).toHaveAttribute("aria-current", "true");
  await expectAudioFor(page, "mock-work-b");
  await expect(notice).toContainText("Ready to listen.");
  await expect(notice.getByRole("button", { name: "Cancel" })).toBeVisible();
  await expectNoStaleSource(page);

  await clickWork(page, "Work A");
  await expect(workButton(page, "Work A")).toHaveAttribute("aria-current", "true");
  await expectAudioFor(page, "mock-work-a");
  await expect(notice).not.toBeVisible();
  await expectNoStaleSource(page);

  await clickWork(page, "Work B");
  await expect(workButton(page, "Work B")).toHaveAttribute("aria-current", "true");
  await expectAudioFor(page, "mock-work-b");
  await expect(notice).toContainText("Ready to listen.");
  await expect(notice.getByRole("button", { name: "Cancel" })).toBeVisible();
  await expectNoStaleSource(page);
});

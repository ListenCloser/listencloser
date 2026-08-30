import { expect, test } from "@playwright/test";
import { mockSession, MOCK_PROJECT_REF, persistSessionScript } from "../fixtures/mockSession";

async function browserNow(page: import("@playwright/test").Page): Promise<number> {
  return page.evaluate(() => performance.now());
}

async function measure(
  page: import("@playwright/test").Page,
  action: () => Promise<void>,
  ready: () => Promise<void>,
): Promise<number> {
  const started = await browserNow(page);
  await action();
  await ready();
  return (await browserNow(page)) - started;
}

test.describe("representation render timing contract (MSW)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
    await page.goto("/");
    await page.waitForFunction(() => navigator.serviceWorker?.controller !== null, undefined, { timeout: 15_000 });
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tab", { name: "Score" })).toBeEnabled({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Spectrogram" })).toBeEnabled({ timeout: 20_000 });
  });

  test("records first-visit and mounted-revisit latency for Score and Spectrogram", async ({ page }, testInfo) => {
    const scoreTab = page.getByRole("tab", { name: "Score" });
    const waveformTab = page.getByRole("tab", { name: "Waveform" });
    const spectrogramTab = page.getByRole("tab", { name: "Spectrogram" });
    const firstScoreMeasure = page.locator(".sheet-music-container g.vf-measure").first();
    const spectrogramCanvas = page.getByTestId("spectrogram-canvas");

    const scoreFirstVisitMs = await measure(
      page,
      () => scoreTab.click(),
      async () => {
        await expect(firstScoreMeasure).toBeVisible({ timeout: 30_000 });
      },
    );

    await waveformTab.click();
    await expect(page.getByTestId("waveform-canvas")).toBeVisible();
    const scoreMountedRevisitMs = await measure(
      page,
      () => scoreTab.click(),
      async () => {
        await expect(firstScoreMeasure).toBeVisible();
      },
    );

    await waveformTab.click();
    await expect(page.getByTestId("waveform-canvas")).toBeVisible();
    const spectrogramFirstVisitMs = await measure(
      page,
      () => spectrogramTab.click(),
      async () => {
        await expect(spectrogramCanvas).toHaveAttribute("data-spectrogram-state", "ready", { timeout: 30_000 });
      },
    );

    await waveformTab.click();
    await expect(page.getByTestId("waveform-canvas")).toBeVisible();
    const spectrogramMountedRevisitMs = await measure(
      page,
      () => spectrogramTab.click(),
      async () => {
        await expect(spectrogramCanvas).toHaveAttribute("data-spectrogram-state", "ready");
      },
    );

    const timings = {
      score_first_visit_ms: Math.round(scoreFirstVisitMs * 10) / 10,
      score_mounted_revisit_ms: Math.round(scoreMountedRevisitMs * 10) / 10,
      spectrogram_first_visit_ms: Math.round(spectrogramFirstVisitMs * 10) / 10,
      spectrogram_mounted_revisit_ms: Math.round(spectrogramMountedRevisitMs * 10) / 10,
    };

    console.log(`REPRESENTATION_RENDER_TIMINGS ${JSON.stringify(timings)}`);
    await testInfo.attach("representation-render-timings.json", {
      body: Buffer.from(JSON.stringify(timings, null, 2)),
      contentType: "application/json",
    });

    // Keep this measurement lane informative rather than flaky: hosted CI is
    // not a stable millisecond benchmark. The deterministic product contract is
    // that a mounted revisit reuses the already-rendered view rather than
    // returning to a loading state.
    expect(await firstScoreMeasure.count()).toBeGreaterThan(0);
    await expect(spectrogramCanvas).toHaveAttribute("data-spectrogram-state", "ready");
  });
});

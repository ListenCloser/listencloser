import { expect, test, type Locator, type Page } from "@playwright/test";
import { mockSession, MOCK_PROJECT_REF, persistSessionScript } from "../fixtures/mockSession";

type ContinuityWindow = typeof window & {
  __pianoRollStaticLayer?: Element;
};

async function pinStaticLayer(layer: Locator) {
  await layer.evaluate((node) => {
    (window as ContinuityWindow).__pianoRollStaticLayer = node;
  });
}

async function expectPinnedStaticLayer(layer: Locator) {
  expect(
    await layer.evaluate((node) => node === (window as ContinuityWindow).__pianoRollStaticLayer),
  ).toBe(true);
}

async function measureUpdate(page: Page, action: () => Promise<void>, settled: () => Promise<void>) {
  const start = await page.evaluate(() => performance.now());
  await action();
  await settled();
  return page.evaluate((startedAt) => Math.round((performance.now() - startedAt) * 10) / 10, start);
}

async function dragPianoRoll(page: Page, svg: Locator) {
  const box = await svg.boundingBox();
  if (!box) throw new Error("piano roll SVG not found");
  const startX = box.x + Math.min(110, box.width * 0.15);
  const endX = Math.min(box.x + box.width - 8, startX + 90);
  const y = box.y + Math.min(80, Math.max(24, box.height / 3));
  await page.mouse.move(startX, y);
  await page.mouse.down();
  await page.mouse.move(endX, y, { steps: 6 });
  await page.mouse.up();
}

test.describe("Piano Roll steady-state continuity (MSW)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(persistSessionScript(), {
      projectRef: MOCK_PROJECT_REF,
      session: mockSession,
    });
  });

  test("keeps the loaded base SVG while transport, selection, and tab visibility change", async ({
    page,
  }, testInfo) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const pianoTab = page.getByRole("tab", { name: "Piano Roll" });
    const scoreTab = page.getByRole("tab", { name: "Score" });
    await expect(pianoTab).toBeEnabled({ timeout: 20_000 });
    await expect(scoreTab).toBeEnabled({ timeout: 20_000 });
    await pianoTab.click();

    const pianoRoll = page.getByTestId("piano-roll");
    const svg = pianoRoll.locator("svg");
    const staticLayer = pianoRoll.locator('[data-piano-roll-static-layer="true"]');
    await expect(pianoRoll).toBeVisible({ timeout: 20_000 });
    await expect(staticLayer).toBeVisible();
    expect(await pianoRoll.locator('[data-note-base="true"]').count()).toBeGreaterThan(0);
    await pinStaticLayer(staticLayer);

    const playbackPosition = page.getByRole("slider", { name: "Playback position" });
    await playbackPosition.focus();
    const transportUpdateMs = await measureUpdate(
      page,
      () => playbackPosition.press("ArrowRight"),
      () => expect(pianoRoll.locator('[data-playhead="true"]')).toBeVisible(),
    );
    await expectPinnedStaticLayer(staticLayer);

    const selectionUpdateMs = await measureUpdate(
      page,
      () => dragPianoRoll(page, svg),
      () => expect(pianoRoll.locator('[data-selection-range="true"]')).toBeVisible(),
    );
    await expectPinnedStaticLayer(staticLayer);

    await scoreTab.click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
    await pianoTab.click();
    await expect(pianoRoll).toBeVisible();
    await expectPinnedStaticLayer(staticLayer);
    await expect(pianoRoll.locator('[data-selection-range="true"]')).toBeVisible();

    const timings = {
      environment: "playwright-msw-ci",
      note: "Steady-state diagnostics only. Cold and mounted-revisit render timing is measured separately by representation-render-timings.spec.ts.",
      transport_overlay_update_ms: transportUpdateMs,
      selection_overlay_update_ms: selectionUpdateMs,
    };
    console.log(`PIANO_ROLL_STEADY_TIMINGS ${JSON.stringify(timings)}`);
    await testInfo.attach("piano-roll-steady-timings.json", {
      body: Buffer.from(JSON.stringify(timings, null, 2)),
      contentType: "application/json",
    });
  });
});

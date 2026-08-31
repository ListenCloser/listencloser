import { expect, test, type Locator, type Page } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

async function expectTouchHeight(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.height).toBeGreaterThanOrEqual(43);
}

async function openPhoneWorkspace(page: Page) {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
}

test("phone workspace stages supporting surfaces around a touch-safe canvas", async ({ page }) => {
  await openPhoneWorkspace(page);

  // Compact layout starts on the music itself, not with desktop side panels
  // covering a narrow canvas. The Inspector stays mounted for state/performance
  // continuity but is visually staged until explicitly opened.
  const libraryTrigger = page.getByRole("button", { name: "Show library", exact: true });
  const breakdownTrigger = page.getByRole("button", { name: "Show breakdown", exact: true });
  await expect(libraryTrigger).toBeVisible();
  await expect(breakdownTrigger).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Breakdown", exact: true })).not.toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await expectTouchHeight(libraryTrigger);
  await expectTouchHeight(breakdownTrigger);
  await expectTouchHeight(page.getByRole("tab", { name: "Waveform", exact: true }));
  await expectTouchHeight(page.getByRole("button", { name: /Playback source:/ }));
  await expectTouchHeight(page.getByRole("button", { name: "Play", exact: true }));
  await expectTouchHeight(page.getByRole("button", { name: "Toggle selected passage loop", exact: true }));

  // Library is an explicit touch destination and its only destructive command
  // is direct rather than hidden behind a one-item overflow menu.
  await libraryTrigger.click();
  const importButton = page.getByRole("button", { name: "Import audio", exact: true });
  const deleteButton = page.getByRole("button", { name: "Delete Test Work", exact: true });
  await expect(importButton).toBeVisible();
  await expectTouchHeight(importButton);
  await expect(deleteButton).toBeVisible();
  await expectTouchHeight(deleteButton);
  await page.getByRole("button", { name: "Hide library", exact: true }).click();

  // Breakdown / Ask is a phone bottom sheet above a viewport-docked transport.
  await breakdownTrigger.click();
  const inspector = page.locator(".studio-inspector-v3");
  const transport = page.locator(".transport-bar-v3");
  await expect(inspector).toHaveClass(/is-open/);
  await expect(page.getByRole("tab", { name: "Breakdown", exact: true })).toBeVisible();
  await expect
    .poll(
      async () => {
        const inspectorBox = await inspector.boundingBox();
        const transportBox = await transport.boundingBox();
        if (!inspectorBox || !transportBox) return false;
        const viewportHeight = await page.evaluate(() => window.innerHeight);
        return (
          inspectorBox.width >= 385 &&
          inspectorBox.y + inspectorBox.height <= transportBox.y + 2 &&
          transportBox.height >= 118 &&
          transportBox.height <= 122 &&
          Math.abs(transportBox.y + transportBox.height - viewportHeight) <= 2
        );
      },
      {
        timeout: 5_000,
        message: "phone Breakdown sheet should settle full-width above a bottom-docked 120px transport",
      },
    )
    .toBe(true);
});

test("phone operation feedback cannot overflow the viewport", async ({ page }) => {
  await openPhoneWorkspace(page);

  // Exercise the production operation-layer classes directly with deliberately
  // long content. This keeps the regression focused on layout rather than job
  // timing and catches the former 360px card + fixed padding overflow.
  await page.evaluate(() => {
    const layer = document.createElement("div");
    layer.className = "operation-layer";
    layer.dataset.testid = "operation-layer-contract";
    layer.innerHTML = `
      <div class="operation-layer-inner">
        <div class="piece-processing-card">
          <span class="piece-processing-filename">an-extremely-long-recording-name-that-must-not-expand-the-phone-viewport.m4a</span>
          <progress value="57" max="100"></progress>
          <span class="piece-processing-stage">Analyzing a deliberately long stage description that should wrap safely · 57%</span>
        </div>
      </div>`;
    document.body.appendChild(layer);
  });

  const layer = page.getByTestId("operation-layer-contract");
  const card = layer.locator(".piece-processing-card");
  await expect(card).toBeVisible();

  const box = await card.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  const filenameOverflow = await layer.locator(".piece-processing-filename").evaluate((element) => {
    const style = getComputedStyle(element);
    return { overflow: style.overflow, textOverflow: style.textOverflow, whiteSpace: style.whiteSpace };
  });
  expect(filenameOverflow).toEqual({ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
});

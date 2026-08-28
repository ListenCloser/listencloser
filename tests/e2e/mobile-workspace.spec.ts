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
  await expect(libraryTrigger).toBeVisible();
  await expect(page.getByRole("button", { name: "Show analysis", exact: true })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Analysis", exact: true })).not.toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await expectTouchHeight(libraryTrigger);
  await expectTouchHeight(page.getByRole("tab", { name: "Waveform", exact: true }));
  await expectTouchHeight(page.getByRole("button", { name: /Playback source:/ }));
  await expectTouchHeight(page.getByRole("button", { name: "Play", exact: true }));
  await expectTouchHeight(page.getByRole("button", { name: "Toggle loop", exact: true }));

  // Library is an explicit touch destination and its only destructive command
  // is direct rather than hidden behind a one-item overflow menu.
  await libraryTrigger.click();
  const deleteButton = page.getByRole("button", { name: "Delete Test Work", exact: true });
  await expect(deleteButton).toBeVisible();
  await expectTouchHeight(deleteButton);
  await page.getByRole("button", { name: "Hide library", exact: true }).click();

  // Analysis / Ask is a phone bottom sheet above a viewport-docked transport.
  await page.getByRole("button", { name: "Show analysis", exact: true }).click();
  const inspector = page.locator(".studio-inspector-v3");
  const transport = page.locator(".transport-bar-v3");
  await expect(inspector).toHaveClass(/is-open/);
  await expect(page.getByRole("tab", { name: "Analysis", exact: true })).toBeVisible();
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
        message: "phone analysis sheet should settle full-width above a bottom-docked 120px transport",
      },
    )
    .toBe(true);
});

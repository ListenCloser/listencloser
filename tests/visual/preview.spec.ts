import { expect, test, type Page } from "@playwright/test";
import { argosScreenshot } from "@argos-ci/playwright";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

async function openMockWorkspace(page: Page) {
  await page.addInitScript(persistSessionScript(), {
    projectRef: MOCK_PROJECT_REF,
    session: mockSession,
  });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible();
}

// Design source-of-truth mockup (lives in design/mockups, uses real tokens).
test("design mockup (SOT)", async ({ page }) => {
  await page.goto(
    "file://" + process.cwd() + "/design/mockups/audio-to-sheet-music.html",
  );
  await page.waitForTimeout(300);
  await argosScreenshot(page, "design-mockup");
});

// Actual built app — landing (auth gate when unauthenticated).
test("app landing", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(400);
  await argosScreenshot(page, "app-landing", { fullPage: true });
});

// V6 changes live in the authenticated creative workspace, so the visual gate
// must cover that surface rather than merely screenshotting the auth gate.
test("app studio — desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openMockWorkspace(page);
  await argosScreenshot(page, "app-studio-desktop", { fullPage: true });

  const harmony = page.locator("details.inspector-evidence-group").filter({ hasText: /^Harmony/ }).first();
  if (await harmony.count()) {
    await harmony.locator("summary").click();
    await argosScreenshot(page, "app-studio-desktop-evidence", { fullPage: true });
  }
});

test("app studio — narrow desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await openMockWorkspace(page);
  await argosScreenshot(page, "app-studio-narrow", { fullPage: true });
});

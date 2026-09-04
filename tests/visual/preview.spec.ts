import { expect, test, type Page } from "@playwright/test";
import { argosScreenshot } from "@argos-ci/playwright";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

async function installMockSession(page: Page) {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
}

async function openDesktopWorkspace(page: Page) {
  await installMockSession(page);
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Breakdown" })).toBeVisible();
}

async function openCompactWorkspace(page: Page) {
  await installMockSession(page);
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Show library" })).toBeVisible();
  await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
}

test("app landing — desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.waitForTimeout(700);
  await expect(page.getByRole("heading", { name: "Listen closer." })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await argosScreenshot(page, "app-landing", { fullPage: true });
});

test("app landing — phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.waitForTimeout(700);
  await expect(page.getByRole("heading", { name: "Listen closer." })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await argosScreenshot(page, "app-landing-phone", { fullPage: true });
});

test("app landing — reduced motion freezes the live signal", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Listen closer." })).toBeVisible();
  const signal = page.locator(".aesthetic-live-signal canvas");
  await expect(signal).toBeVisible();
  await page.waitForTimeout(100);
  const firstFrame = await signal.evaluate((canvas) => (canvas as HTMLCanvasElement).toDataURL());
  await page.waitForTimeout(160);
  const secondFrame = await signal.evaluate((canvas) => (canvas as HTMLCanvasElement).toDataURL());
  expect(secondFrame).toBe(firstFrame);
});

test("app studio — desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openDesktopWorkspace(page);
  await argosScreenshot(page, "app-studio-desktop", { fullPage: true });

  const evidenceRoot = page.locator("details.inspector-breakdown-evidence-root").first();
  if (await evidenceRoot.count()) {
    await evidenceRoot.locator(":scope > summary").click();
    const harmony = evidenceRoot.locator("details.inspector-evidence-group").filter({ hasText: /^Harmony/ }).first();
    if (await harmony.count()) await harmony.locator(":scope > summary").click();
    await argosScreenshot(page, "app-studio-desktop-evidence", { fullPage: true });
  }
});

test("app studio — empty workspace", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openDesktopWorkspace(page);
  await page.getByRole("button", { name: "Delete Test Work" }).click();
  await expect(page.getByRole("heading", { name: "Import a recording" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Import audio" })).toBeVisible();
  await expect(page.getByTestId("empty-workspace-signal")).toBeHidden();
  await argosScreenshot(page, "app-studio-empty-desktop", { fullPage: true });
});

test("app studio — narrow desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await openDesktopWorkspace(page);
  await argosScreenshot(page, "app-studio-narrow", { fullPage: true });
});

test("app studio — tablet", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await openCompactWorkspace(page);
  await argosScreenshot(page, "app-studio-tablet", { fullPage: true });

  await page.getByRole("button", { name: "Show library" }).click();
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible();
  await argosScreenshot(page, "app-studio-tablet-library", { fullPage: true });
});

test("app studio — phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openCompactWorkspace(page);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await argosScreenshot(page, "app-studio-phone", { fullPage: true });

  await page.getByRole("button", { name: "Show library" }).click();
  await expect(page.getByRole("button", { name: "Delete Test Work" })).toBeVisible();
  await argosScreenshot(page, "app-studio-phone-library", { fullPage: true });
  await page.getByRole("button", { name: "Hide library" }).click();

  await expect(page.getByRole("button", { name: "Show breakdown" })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Show breakdown" }).click();
  await expect(page.getByRole("tab", { name: "Breakdown" })).toBeVisible();
  await argosScreenshot(page, "app-studio-phone-analysis", { fullPage: true });
});

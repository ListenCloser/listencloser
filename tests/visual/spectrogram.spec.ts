import { expect, test } from "@playwright/test";
import { argosScreenshot } from "@argos-ci/playwright";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("app studio — Spectrogram ruler", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
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
  const spectrogramTab = page.getByRole("tab", { name: "Spectrogram" });
  await expect(spectrogramTab).toBeEnabled({ timeout: 20_000 });
  await spectrogramTab.click();
  await expect(page.getByTestId("spectrogram-canvas")).toHaveAttribute("data-spectrogram-state", "ready", { timeout: 30_000 });

  await argosScreenshot(page, "app-studio-spectrogram", { fullPage: true });
});

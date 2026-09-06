import { expect, test } from "@playwright/test";
import { argosScreenshot } from "@argos-ci/playwright";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("app studio — Piano Roll hierarchy", async ({ page }) => {
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
  const pianoRollTab = page.getByRole("tab", { name: "Piano Roll" });
  await expect(pianoRollTab).toBeEnabled({ timeout: 20_000 });
  await pianoRollTab.click();
  await expect(page.getByTestId("piano-roll")).toBeVisible();

  await argosScreenshot(page, "app-studio-piano-roll", { fullPage: true });
});

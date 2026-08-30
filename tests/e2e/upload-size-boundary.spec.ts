import { expect, test } from "@playwright/test";

import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

const LEGACY_BROWSER_LIMIT_BYTES = 4 * 1024 * 1024;

test("a supported recording above the legacy 4 MiB ceiling reaches the upload workflow", async ({ page }) => {
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
  await page.reload();

  const importButton = page
    .getByRole("complementary")
    .getByRole("button", { name: "Import audio" });
  await expect(importButton).toBeEnabled({ timeout: 20_000 });

  await page.locator("#audio-import-input").setInputFiles({
    name: "above-legacy-limit.m4a",
    mimeType: "audio/mp4",
    buffer: Buffer.alloc(LEGACY_BROWSER_LIMIT_BYTES + 1),
  });

  await expect(page.getByText("Audio files must be 4 MB or smaller.")).not.toBeVisible();
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: /Playback source:/ })).toBeVisible({ timeout: 20_000 });
});

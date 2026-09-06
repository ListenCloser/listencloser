import { expect, test, type Page } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

async function openWorkspace(page: Page) {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("A minor", { exact: true })).toBeVisible();
}

test("Production / Space stays opt-in and exposes only method-qualified measured relations", async ({ page }) => {
  await openWorkspace(page);

  const lens = page.getByRole("region", { name: "Production and spatial analysis" });
  await expect(lens).toBeVisible();
  await lens.getByRole("button", { name: "+ Production / Space", exact: true }).click();

  await expect(lens.getByText("Production / Space", { exact: true })).toBeVisible();
  await expect(lens.getByText("Experimental", { exact: true })).toBeVisible();
  await expect(lens.getByText(/literal loudness, stereo mid\/side, spectral, and transient changes/i)).toBeVisible();
  await lens.getByRole("button", { name: "Add", exact: true }).click();

  await expect(lens.getByText("Loudness", { exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(lens.getByText("+8.2 LUFS", { exact: true })).toBeVisible();
  await expect(lens.getByText("Side energy share", { exact: true })).toBeVisible();
  await expect(lens.getByText("+22.5 percentage points", { exact: true })).toBeVisible();
  await expect(lens.getByText("Spectral centroid", { exact: true })).toBeVisible();
  await expect(lens.getByText("Onset strength", { exact: true })).toBeVisible();

  const loudness = lens.locator("article").filter({ hasText: "Loudness" });
  await loudness.getByText("Method", { exact: true }).click();
  await expect(loudness.getByText(/pyloudnorm BS\.1770 integrated loudness per fixed window/)).toBeVisible();
  await expect(loudness.getByText(/Compared 0:03–0:06 → 0:06–0:09/)).toBeVisible();
  await expect(loudness.getByText(/Source Version: mock-version-1/)).toBeVisible();

  await expect(lens.getByText(/warm|bright|wide|punchy|better mix|section boundary/i)).toHaveCount(0);
});

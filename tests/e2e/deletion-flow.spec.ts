import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("deleting the active work clears it from the library", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );

  await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });

  // Click the delete affordance (×), then confirm (🗑).
  await page.getByTitle("Delete work").click();
  await page.getByTitle("Click again to confirm delete").click();

  // The work should disappear from the library and show the empty state.
  await expect(page.getByRole("button", { name: "Test Work" })).toHaveCount(0);
  await expect(page.getByText(/Imported works will appear here/)).toBeVisible();
});

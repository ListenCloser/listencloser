import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("deleting the active work clears it and leaves no stale transport state", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );

  await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });

  // The work must be open and playable first: an enabled seek slider proves a
  // real source and a non-zero duration were loaded (it is disabled whenever
  // there is no source or no duration).
  const seek = page.getByRole("slider", { name: "Playback position" });
  await expect(seek).toBeEnabled({ timeout: 20_000 });

  // Click the delete affordance (×), then confirm (🗑).
  await page.getByTitle("Delete work").click();
  await page.getByTitle("Click again to confirm delete").click();

  // The work should disappear from the library immediately (optimistic) and
  // show the empty state.
  await expect(page.getByRole("button", { name: "Test Work" })).toHaveCount(0);
  await expect(page.getByText(/Imported works will appear here/)).toBeVisible();

  // No stale transport state: playback is disabled, the playhead is at 0:00,
  // and the previously-loaded duration is cleared rather than left behind.
  await expect(seek).toBeDisabled();
  const times = page.locator(".transport-time span");
  await expect(times.nth(0)).toHaveText("0:00");
  await expect(times.nth(1)).toHaveText("0:00");
});

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

  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

  // The work must be open and playable first: an enabled seek slider proves a
  // real source and a non-zero duration were loaded (it is disabled whenever
  // there is no source or no duration).
  const seek = page.getByRole("slider", { name: "Playback position" });
  await expect(seek).toBeEnabled({ timeout: 20_000 });

  await page.getByRole("button", { name: "More actions for Test Work" }).click();
  await page.getByRole("menuitem", { name: "Delete recording" }).click();

  // The work should disappear from the library immediately (optimistic) and
  // show the empty state.
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Import a recording" })).toBeVisible();

  // No stale transport state: deleting the active work removes the source
  // controls entirely rather than leaving a disabled playhead behind.
  await expect(page.getByRole("slider", { name: "Playback position" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Playback source:/ })).toHaveCount(0);
});

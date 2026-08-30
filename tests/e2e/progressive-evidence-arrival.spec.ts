import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("a durable recording stays usable while understand artifacts arrive", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  // On the first-ever mocked page load, MSW registration can finish just after
  // the one-shot processing-health request. Reload once with the active worker
  // controlling navigation so every API precondition is deterministically mocked.
  await page.reload();

  const importButton = page.getByRole("complementary").getByRole("button", { name: "Import audio" });
  await expect(importButton).toBeVisible({ timeout: 20_000 });
  // Import is processing-dependent. Do not race the initial health check: the
  // control becomes enabled only after the queue endpoint confirms readiness.
  await expect(importButton).toBeEnabled({ timeout: 10_000 });
  await importButton.click();
  await page.getByRole("menuitem", { name: /Upload recording/ }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "progressive-fixture.m4a",
    mimeType: "audio/mp4",
    buffer: Buffer.from("mock progressive m4a payload"),
  });

  // Upload durability ends the blocking phase. The real source is already a
  // usable Work while the understand job is still running.
  await expect(page.getByText("Recording saved.", { exact: true })).toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Playback source:/ })).toBeVisible();
  await expect(page.locator(".operation-layer")).not.toBeVisible();

  // The mock Work bundle intentionally exposes only the durable source during
  // the first processing polls. Keep the complete representation navigation in
  // place instead of inserting Piano Roll / Score later; unavailable views are
  // disabled until the source-of-truth bundle actually exposes their payloads.
  const representationTabs = page.getByRole("tablist", { name: "Music representation" });
  const pianoRollTab = representationTabs.getByRole("tab", { name: "Piano Roll" });
  const scoreTab = representationTabs.getByRole("tab", { name: "Score" });
  await expect(representationTabs.getByRole("tab")).toHaveCount(4);
  await expect(pianoRollTab).toBeVisible();
  await expect(scoreTab).toBeVisible();
  await expect(pianoRollTab).toBeDisabled();
  await expect(scoreTab).toBeDisabled();

  // When the backend bundle actually exposes new artifacts, the same tabs
  // become interactive without stealing the active representation or source.
  await expect(pianoRollTab).toBeEnabled({ timeout: 10_000 });
  await expect(scoreTab).toBeEnabled({ timeout: 10_000 });
  await expect(representationTabs.getByRole("tab")).toHaveCount(4);
  await expect(page.getByRole("tab", { name: "Waveform" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();
  await expect(page.getByText("Recording saved.", { exact: true })).not.toBeVisible({ timeout: 5_000 });
});

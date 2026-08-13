import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("a persisted work reopens with synchronized musical workspace views", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );

  await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });

  // The playback sources are human labels, never internal artifact ids.
  await expect(page.getByText("Hearing", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Original", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Transcription", exact: true })).toBeVisible();

  // The four representations are discoverable from the tab bar.
  await expect(page.getByRole("tab", { name: "Listen" })).toBeVisible();
  await page.getByRole("tab", { name: "Piano roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible();
  await expect(page.getByText(/42 notes/)).toBeVisible();
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible();
  await page.getByRole("tab", { name: "Analysis" }).click();
  await expect(page.getByText("A minor")).toBeVisible();
  await expect(page.getByText("112 BPM")).toBeVisible();
});

test("import starts one durable understand job and reloads the persisted work", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  const importButton = page.getByRole("complementary").getByRole("button", { name: "Import audio" });
  await expect(importButton).toBeVisible({ timeout: 20_000 });

  await importButton.click();
  const realAudio = process.env.REAL_AUDIO_FILE;
  await page.locator('input[type="file"]').setInputFiles(
    realAudio && existsSync(realAudio)
      ? realAudio
      : { name: "fixture.m4a", mimeType: "audio/mp4", buffer: Buffer.from("mock m4a payload") },
  );

  await expect(page.getByText(/You can close this page/)).toBeVisible();
  await expect(page.getByRole("tab", { name: "Piano roll" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByRole("button", { name: "Transcription", exact: true })).toBeVisible({
    timeout: 20_000,
  });
});

test("score appears as a playback source and follows the transport", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });

  // A notation-derived render exists, so Score is a selectable source.
  await expect(page.getByRole("button", { name: "Score", exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible();
  await expect(page.getByText("Select Score in the transport to hear this notation (notation time).")).toBeVisible();

  await page.getByRole("button", { name: "Score", exact: true }).click();
  await expect(page.getByText("Playing the score in notation time. Click a measure to jump.")).toBeVisible();
});

test("signed-out users see the sign-in gate, not the importer", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => navigator.serviceWorker?.controller !== null, undefined, { timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Import audio" })).not.toBeVisible();
});

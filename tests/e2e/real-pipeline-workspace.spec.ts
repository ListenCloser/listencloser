import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("a persisted work reopens with transcription, score, analysis, and shortcuts", async ({
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
  await expect(page.getByText("42 detected notes")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Generated from MIDI")).toBeVisible({ timeout: 20_000 });

  await page.getByRole("tab", { name: "Insights" }).click();
  await expect(page.getByText("A minor")).toBeVisible();
  await expect(page.getByText("112 BPM")).toBeVisible();

  await page.getByRole("tab", { name: "Shortcuts" }).click();
  await page.getByLabel("Work command").fill("summarize");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText(/Key: A minor/)).toBeVisible();
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
  await expect(page.getByText("42 detected notes")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Generated from MIDI")).toBeVisible({
    timeout: 20_000,
  });

});

test("signed-out users cannot accidentally open the importer", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => navigator.serviceWorker?.controller !== null, undefined, { timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Sign in to begin" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
  await expect(page.getByText("Service online")).toBeVisible();
});

import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("a persisted work reopens with transcription, score, analysis, and commands", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(mockSession), MOCK_PROJECT_REF);
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );

  await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("42 detected notes")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Generated from MIDI")).toBeVisible({ timeout: 20_000 });

  await page.getByRole("button", { name: "Insights" }).click();
  await expect(page.getByText("A minor")).toBeVisible();
  await expect(page.getByText("112 BPM")).toBeVisible();

  await page.getByRole("button", { name: "Commands" }).click();
  await page.getByLabel("Work command").fill("summarize");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText(/Key: A minor/)).toBeVisible();
});

test("import starts one durable understand job and reloads the persisted work", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(mockSession), MOCK_PROJECT_REF);
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: "Import audio" })).toBeVisible({ timeout: 20_000 });

  await page.getByRole("button", { name: "Import audio" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "fixture.wav",
    mimeType: "audio/wav",
    buffer: Buffer.from("RIFF...."),
  });

  await expect(page.getByText(/You can close this page/)).toBeVisible();
  await expect(page.getByText("42 detected notes")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Generated from MIDI")).toBeVisible({
    timeout: 20_000,
  });

});

import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("upload renders persisted transcription, score, and analysis results", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(mockSession), MOCK_PROJECT_REF);
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );

  const input = page.locator('input[type="file"]');
  await expect(page.getByText("Drop an audio file to start")).toBeVisible();
  await input.setInputFiles({
    name: "fixture.wav",
    mimeType: "audio/wav",
    buffer: Buffer.from("RIFF...."),
  });

  await expect(page.getByText("42 detected notes")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Generated from MIDI")).toBeVisible({
    timeout: 20_000,
  });

  await page.getByRole("button", { name: "Insights" }).click();
  await expect(page.getByText("A minor")).toBeVisible();
  await expect(page.getByText("112 BPM")).toBeVisible();
});

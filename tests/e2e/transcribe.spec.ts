import { test, expect } from "@playwright/test";

test.describe("P3: transcribe an uploaded audio file", () => {
  test("user uploads audio and the piano roll renders notes", async ({
    page,
  }) => {
    // The transcribe/analyze APIs are mocked by MSW (NEXT_PUBLIC_MOCK_ENABLED).
    await page.goto("/?tab=transcribe");
    // The file input is visually hidden; wait for the visible "Upload file" card.
    await page.getByText("Upload file").waitFor({ timeout: 15_000 });

    // Wait for MSW service worker to be ready
    await page.waitForFunction(() => navigator.serviceWorker?.controller !== null, { timeout: 10_000 });

    await page.locator(".source-card input[type='file']").first().setInputFiles({
      name: "direct.wav",
      mimeType: "audio/wav",
      buffer: Buffer.from("RIFF...."),
    });

    await expect(page.getByTestId("piano-roll")).toBeVisible({
      timeout: 20_000,
    });

    const notes = page.getByTestId("piano-roll").locator("rect");
    expect(await notes.count()).toBeGreaterThan(0);

    await expect(page.getByText(/Download MIDI/)).toBeVisible();
  });
});

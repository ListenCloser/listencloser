import { test, expect, type Page } from "@playwright/test";

const SAMPLE = {
  name: "direct.wav",
  mimeType: "audio/wav",
  buffer: Buffer.from("RIFF...."),
};

async function openStudio(page: Page) {
  await page.goto("/");
  await page.locator(".nav").first().waitFor({ timeout: 15_000 });
}

test.describe("Supported user paths", () => {
  test("P1: anonymous visitor lands on / without crashing (Studio in bypass mode)", async ({
    page,
  }) => {
    await openStudio(page);

    const crashed = await page.locator("text=Application error").count();
    expect(crashed).toBe(0);

    await expect(page.locator(".nav")).toBeVisible();
  });

  test("P2: a signed-in (mocked) session renders Studio", async ({ page }) => {
    await openStudio(page);

    await expect(page.locator(".nav")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Upload|Record/ }),
    ).toBeVisible();
  });

  test("P3: transcribe a file → piano roll + audio (mocked backend)", async ({
    page,
  }) => {
    await page.goto("/?tab=transcribe");
    await page.getByText("Upload file").waitFor({ timeout: 15_000 });

    // Wait for MSW service worker to be ready
    await page.waitForFunction(() => navigator.serviceWorker?.controller !== null, { timeout: 10_000 });

    await page
      .locator(".source-card input[type='file']")
      .first()
      .setInputFiles(SAMPLE);

    await expect(page.getByTestId("piano-roll")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText(/Download MIDI/)).toBeVisible();
  });
});

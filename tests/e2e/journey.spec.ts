import { test, expect } from "@playwright/test";

const SAMPLE = {
  name: "direct.wav",
  mimeType: "audio/wav",
  buffer: Buffer.from("RIFF...."),
};

test.describe("User journeys", () => {
  test("Library: renders upload target, record control, and empty state", async ({
    page,
  }) => {
    await page.goto("/?tab=library");
    await page.locator(".drop-zone").first().waitFor({ timeout: 15_000 });

    await expect(page.locator(".drop-zone").first()).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Record/ }),
    ).toBeVisible();
    await expect(page.getByText(/Drop audio.*save/i)).toBeVisible();
    await expect(page.getByText(/No tracks yet/i)).toBeVisible();
  });

  test("Library: record button shows recording state", async ({ page }) => {
    // Mock getUserMedia so the Record button triggers recording state.
    await page.addInitScript(() => {
      const audioTrack = { kind: "audio", enabled: true, stop: () => {} };
      Object.defineProperty(navigator, "mediaDevices", {
        value: {
          getUserMedia: () =>
            Promise.resolve({
              getTracks: () => [audioTrack],
              getAudioTracks: () => [audioTrack],
            }),
        },
        configurable: true,
      });
    });

    // Mock MediaRecorder so recording starts without a real mic.
    await page.addInitScript(() => {
      class MockRecorder {
        mimeType = "audio/webm";
        state = "inactive";
        ondataavailable: any = null;
        onstop: any = null;
        start() {
          this.state = "recording";
        }
        stop() {
          this.state = "inactive";
          if (typeof this.ondataavailable === "function") {
            this.ondataavailable({
              data: new Blob(["fake"], { type: "audio/webm" }),
            });
          }
          if (typeof this.onstop === "function") this.onstop();
        }
        static isTypeSupported() {
          return true;
        }
      }
      window.MediaRecorder = MockRecorder as any;
    });

    await page.goto("/?tab=library");
    await page.locator(".drop-zone").first().waitFor({ timeout: 15_000 });

    const recordBtn = page.getByRole("button", { name: /Record/ });
    await expect(recordBtn).toBeVisible();
    await recordBtn.click();
    await page.waitForTimeout(300);

    await expect(page.getByRole("button", { name: /Stop/ })).toBeVisible();
    await expect(page.locator(".record-dot")).toBeVisible();
    await expect(page.locator(".status")).toContainText("Recording");
  });

  test("Transcribe: upload → piano roll + MIDI playback", async ({ page }) => {
    // Transcribe/analyze APIs are mocked by MSW (NEXT_PUBLIC_MOCK_ENABLED).
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

  test("Transcribe: Analyze button → analysis view", async ({ page }) => {
    await page.goto("/?tab=transcribe");
    await page.getByText("Upload file").waitFor({ timeout: 15_000 });

    // Wait for MSW service worker to be ready
    await page.waitForFunction(() => navigator.serviceWorker?.controller !== null, { timeout: 10_000 });

    await page
      .locator(".source-card input[type='file']")
      .first()
      .setInputFiles(SAMPLE);

    // Wait for the populated result, then trigger analysis from the Transcribe tab.
    const analyzeBtn = page.locator("button.btn-primary");
    await expect(analyzeBtn).toBeVisible({ timeout: 20_000 });
    await analyzeBtn.click();

    // Analysis view renders key/tempo/time-signature stats.
    await expect(page.locator(".stat").first()).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText(/Diatonic chords/i)).toBeVisible();
  });
});

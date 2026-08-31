import { expect, test } from "@playwright/test";
import { mockSession, MOCK_PROJECT_REF, persistSessionScript } from "../fixtures/mockSession";

async function openSpectrogram(page: import("@playwright/test").Page) {
  await page.getByRole("tab", { name: "Spectrogram" }).click();
  const canvas = page.getByTestId("spectrogram-canvas");
  await expect(canvas).toBeVisible();
  await expect(canvas).toHaveAttribute("aria-valuetext", /seconds/, { timeout: 20_000 });
  return canvas;
}

test.describe("synchronized spectrogram (MSW)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
    await page.goto("/");
    await page.waitForFunction(() => navigator.serviceWorker?.controller !== null, undefined, { timeout: 15_000 });
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
  });

  test("is directly available and preserves shared seek and selection", async ({ page }) => {
    const canvas = await openSpectrogram(page);
    const box = await canvas.boundingBox();
    if (!box) throw new Error("spectrogram canvas not found");

    // A click at the midpoint seeks the shared transport.
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    const seek = page.getByRole("slider", { name: "Playback position" });
    await expect.poll(async () => Number(await seek.inputValue())).toBeGreaterThan(0);

    // A horizontal drag creates the shared performance-time selection and
    // enables the one canonical passage-loop control.
    await page.mouse.move(box.x + box.width * 0.2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.65, box.y + box.height / 2, { steps: 6 });
    await page.mouse.up();
    const loop = page.getByRole("button", { name: "Toggle selected passage loop" });
    await expect(loop).toBeVisible();
    await expect(loop).toBeEnabled();
    await expect(page.getByRole("button", { name: "Loop selection" })).toHaveCount(0);

    // Core views retain the same selection and transport position.
    const position = await seek.inputValue();
    await page.getByRole("tab", { name: "Waveform" }).click();
    await expect(page.getByTestId("waveform-canvas")).toBeVisible();
    await expect(seek).toHaveValue(position);
    await openSpectrogram(page);
    await expect(loop).toBeEnabled();
  });
});

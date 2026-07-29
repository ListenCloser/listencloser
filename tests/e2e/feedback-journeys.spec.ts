import { test, expect } from "@playwright/test";
import path from "path";

test.describe("FL-J01: Real-audio happy path", () => {
  test("J01: workspace loads → upload triggers processing → transport + representations appear", async ({ page }) => {
    await page.goto("/workspace");
    await expect(page.getByText("Drop an audio file to start")).toBeVisible({ timeout: 15_000 });

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByText("Drop an audio file to start").click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(path.resolve("backend/tests/fixtures/sine_a4_c5.wav"));

    await expect(page.getByRole("button", { name: "▶" })).toBeVisible({ timeout: 30_000 });

    await expect(page.getByText("Piano Roll", { exact: false })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Waveform", { exact: false })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("42 notes")).toBeVisible({ timeout: 5_000 });

    await expect(page.getByRole("button", { name: "Explore" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Correct" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Compare" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create" })).toBeVisible();

    const playBtn = page.getByRole("button", { name: "▶" });
    await expect(playBtn).toBeVisible();

    await expect(page.getByText("Selection")).toBeVisible();
    await expect(page.getByText("Properties")).toBeVisible();
    await expect(page.getByText("120 BPM")).toBeVisible();
  });
});

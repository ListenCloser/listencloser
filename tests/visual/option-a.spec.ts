import { expect, test } from "@playwright/test";
import { argosScreenshot } from "@argos-ci/playwright";

test("design lab — option A desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/design-lab/option-a");
  await expect(page.getByText("LISTEN CLOSER")).toBeVisible();
  await expect(page.getByText("Harmonic tension increases.")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await argosScreenshot(page, "design-option-a-desktop", { fullPage: true });
});

test("design lab — option A phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/design-lab/option-a");
  await expect(page.getByText("LISTEN CLOSER")).toBeVisible();
  await expect(page.getByRole("button", { name: "WAVEFORM" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await argosScreenshot(page, "design-option-a-phone", { fullPage: true });
});

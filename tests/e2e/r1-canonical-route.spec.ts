import { test, expect } from "@playwright/test";

test.describe("R1/R2: Canonical route", () => {
  test("root route (/) shows the music workspace with piano roll", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Piano Roll")).toBeVisible({ timeout: 15_000 });
  });
});

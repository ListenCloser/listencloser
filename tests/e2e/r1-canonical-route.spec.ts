import { test, expect } from "@playwright/test";

test.describe("R1: Canonical route", () => {
  test("root route (/) should show the music workspace, not a tabbed tool shell", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Drop an audio file to start")).toBeVisible({ timeout: 15_000 });
  });
});

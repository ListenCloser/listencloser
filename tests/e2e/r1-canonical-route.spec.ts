import { test, expect } from "@playwright/test";

test.describe("R1/R2: Canonical route", () => {
  test("root route (/) shows the workspace shell with transport and mode selector", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("hello-ai")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "▶" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Explore" })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("120 BPM")).toBeVisible({ timeout: 5_000 });
  });
});

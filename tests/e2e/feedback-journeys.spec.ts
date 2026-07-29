import { test, expect } from "@playwright/test";

test.describe("FL-J01: Workspace shell", () => {
  test("root / shows workspace with transport, mode selector, import prompt", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("hello-ai")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Explore" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Correct" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Compare" })).toBeVisible();

    await expect(page.getByRole("button", { name: "▶" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("120 BPM")).toBeVisible();

    await expect(page.getByText("No representations yet")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByRole("button", { name: "Import Audio" })).toBeVisible();
  });
});

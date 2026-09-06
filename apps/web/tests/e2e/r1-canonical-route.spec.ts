import { expect, test } from "@playwright/test";

test.describe("canonical workspace route", () => {
  test("root shows an honest authentication gate", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Listen closer." })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Continue with Google" }).first()).toBeVisible();
  });
});

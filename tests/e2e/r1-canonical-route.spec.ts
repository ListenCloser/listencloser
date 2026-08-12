import { expect, test } from "@playwright/test";

test.describe("canonical workspace route", () => {
  test("root shows an honest authentication gate", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Music Lab")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Sign in with Google" }).first()).toBeVisible();
  });
});

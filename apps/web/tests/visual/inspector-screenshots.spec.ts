import { test } from "@playwright/test";

test.describe("inspector screenshots", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
  });

  test("app landing page", async ({ page }) => {
    await page.goto("/");
    await page.waitForTimeout(500);
    await page.screenshot({
      path: "docs/pr/inspector-context-screenshots/01-app-landing.png",
      fullPage: true,
    });
  });

  test("auth gate (studio without backend)", async ({ page }) => {
    await page.goto("/");
    await page.waitForTimeout(500);
    await page.screenshot({
      path: "docs/pr/inspector-context-screenshots/02-auth-gate.png",
      fullPage: true,
    });
  });
});

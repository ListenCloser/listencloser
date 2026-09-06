import { expect, test } from "@playwright/test";
import { argosScreenshot } from "@argos-ci/playwright";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("Ask composer has an inset prompt arrow and horizontal send affordance", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(persistSessionScript(), {
    projectRef: MOCK_PROJECT_REF,
    session: mockSession,
  });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

  await page.getByRole("tab", { name: "Ask" }).click();

  const send = page.getByRole("button", { name: "Send question" });
  await expect(send).toBeVisible();
  const sendBox = await send.boundingBox();
  expect(sendBox).not.toBeNull();
  expect(sendBox!.width).toBeGreaterThan(sendBox!.height);
  expect(sendBox!.width).toBeGreaterThanOrEqual(40);

  const prompt = page.locator(".ask-prompt").first();
  await expect(prompt).toBeVisible();
  const arrowInset = await prompt.evaluate((element) => (
    Number.parseFloat(getComputedStyle(element, "::after").paddingRight)
  ));
  expect(arrowInset).toBeGreaterThanOrEqual(8);

  await argosScreenshot(page, "app-studio-ask-affordances", { fullPage: true });
});

import { expect, test, type Page } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

async function openWorkspace(page: Page) {
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
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible();
}

test("symbolic detail is an opt-in experimental Inspector analysis", async ({ page }) => {
  await openWorkspace(page);

  const inspector = page.locator("aside.inspector");
  await expect(inspector).toBeVisible();
  const addAnalysisButton = inspector.getByRole("button", {
    name: "+ Add analysis",
    exact: true,
  }).first();
  await expect(addAnalysisButton).toBeVisible();
  await addAnalysisButton.click();

  await expect(inspector.getByText("Symbolic detail", { exact: true })).toBeVisible();
  await expect(inspector.getByText("Experimental", { exact: true })).toBeVisible();
  await expect(inspector.getByText(
    "Measure register, contour, interval motion, density, and texture from this MIDI.",
    { exact: true },
  )).toBeVisible();
  await expect(inspector.getByRole("button", { name: "Add", exact: true })).toBeVisible();
});

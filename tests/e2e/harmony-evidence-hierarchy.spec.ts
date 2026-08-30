import { expect, test, type Page } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

async function openWorkspace(page: Page) {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("A minor", { exact: true })).toBeVisible();
}

async function openHarmonyEvidence(page: Page) {
  const evidenceRoot = page.locator(".inspector-breakdown-evidence-root");
  await evidenceRoot.locator(":scope > summary").click();
  const harmonyDisclosure = page.locator(".inspector-evidence-group").filter({ hasText: "Harmony" });
  await expect(harmonyDisclosure).toBeVisible();
  await expect(harmonyDisclosure.locator(":scope > summary")).toContainText("Chord timeline");
  await harmonyDisclosure.locator(":scope > summary").click();
  return page.getByRole("table", { name: "Harmonic evidence timeline" });
}

test("harmony evidence keeps chord primary and discloses theory context progressively", async ({ page }) => {
  await openWorkspace(page);
  const table = await openHarmonyEvidence(page);

  await expect(table).toBeVisible();
  await expect(table.getByRole("columnheader")).toHaveText(["Time", "Harmony"]);
  await expect(table.getByRole("row")).toHaveCount(7);

  // Key remains promoted once in Context. Degree/function are secondary labels
  // inside the single Harmony column instead of permanent empty columns.
  await expect(table.getByText("Degree", { exact: true }).first()).toBeVisible();
  await expect(table.getByRole("button", { name: "I", exact: true }).first()).toBeVisible();
  await expect(table.getByText("Tonic", { exact: true }).first()).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Degree" })).toHaveCount(0);
  await expect(table.getByRole("columnheader", { name: "Function" })).toHaveCount(0);

  // Full claims/provenance are still available one level deeper rather than
  // being repeated in the default scan path.
  const firstRowDetails = table.getByText("Evidence details", { exact: true }).first();
  await firstRowDetails.click();
  await expect(table.getByText(/I \(A minor\)/).first()).toBeVisible();
});

test("breakdown remains prioritized and evidence fits a constrained inspector", async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 760 });
  await openWorkspace(page);

  const promotedFindings = page.locator(".inspector-breakdown-findings > .inspector-breakdown-finding");
  const promotedCount = await promotedFindings.count();
  expect(promotedCount).toBeGreaterThan(0);
  expect(promotedCount).toBeLessThanOrEqual(3);

  const moreDisclosure = page.getByText(/More findings/, { exact: false });
  if (await moreDisclosure.count()) {
    await moreDisclosure.first().click();
    await expect(page.locator(".inspector-breakdown-finding")).toHaveCount(
      await page.locator(".inspector-breakdown-finding").count(),
    );
  }

  const table = await openHarmonyEvidence(page);
  await expect(table).toBeVisible();
  const fitsInspector = await table.evaluate((element) => element.scrollWidth <= element.clientWidth + 1);
  expect(fitsInspector).toBe(true);
  await expect(table.getByRole("columnheader")).toHaveText(["Time", "Harmony"]);
});

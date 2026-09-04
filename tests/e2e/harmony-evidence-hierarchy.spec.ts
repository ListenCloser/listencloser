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

async function openHarmonyAnalysis(page: Page) {
  const analysisSummary = page.getByText("Analysis", { exact: true });
  await expect(analysisSummary).toBeVisible();
  await analysisSummary.click();

  const harmony = page.getByRole("region", { name: "Harmony analysis" });
  await expect(harmony).toBeVisible();
  return harmony.getByRole("table", { name: "Harmonic analysis timeline" });
}

test("harmony analysis keeps chord primary with flat theory context", async ({ page }) => {
  await openWorkspace(page);
  const table = await openHarmonyAnalysis(page);

  await expect(table).toBeVisible();
  await expect(table.getByRole("columnheader")).toHaveText(["Time", "Harmony"]);
  await expect(table.getByRole("row")).toHaveCount(7);

  // Key remains promoted once in Overview. Degree/function are secondary labels
  // inside the single Harmony column instead of permanent empty columns.
  await expect(table.getByText("Degree", { exact: true }).first()).toBeVisible();
  await expect(table.getByRole("button", { name: "I", exact: true }).first()).toBeVisible();
  await expect(table.getByText("Tonic", { exact: true }).first()).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Degree" })).toHaveCount(0);
  await expect(table.getByRole("columnheader", { name: "Function" })).toHaveCount(0);

  // Provenance stays in the underlying evidence contract; the default timeline
  // does not repeat a nested Evidence details disclosure on every row.
  await expect(table.getByText("Evidence details", { exact: true })).toHaveCount(0);
});

test("breakdown remains prioritized and analysis fits a constrained inspector", async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 760 });
  await openWorkspace(page);

  // Some deterministic fixtures legitimately have no localized finding. When
  // findings exist, only the first three may be in the default scan path.
  const promotedFindings = page.locator(".inspector-breakdown-findings > .inspector-breakdown-finding");
  const promotedCount = await promotedFindings.count();
  expect(promotedCount).toBeLessThanOrEqual(3);

  const moreDisclosure = page.locator("details").filter({ has: page.getByText(/More findings/, { exact: false }) }).first();
  if (await moreDisclosure.count()) {
    const hiddenFindings = moreDisclosure.locator(".inspector-breakdown-finding");
    expect(await hiddenFindings.count()).toBeGreaterThan(0);
    await expect(hiddenFindings.first()).not.toBeVisible();
    await moreDisclosure.locator(":scope > summary").click();
    await expect(hiddenFindings.first()).toBeVisible();
  }

  const table = await openHarmonyAnalysis(page);
  await expect(table).toBeVisible();
  const fitsInspector = await table.evaluate((element) => element.scrollWidth <= element.clientWidth + 1);
  expect(fitsInspector).toBe(true);
  await expect(table.getByRole("columnheader")).toHaveText(["Time", "Harmony"]);
});
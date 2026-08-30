import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("harmony evidence aligns chord, degree, and function without repeating key context", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );

  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("A minor", { exact: true })).toBeVisible();

  await page.getByText("Evidence details", { exact: true }).click();
  const harmonyDisclosure = page.locator(".inspector-evidence-group").filter({ hasText: "Harmony" });
  await expect(harmonyDisclosure).toBeVisible();
  await harmonyDisclosure.locator("summary").click();

  const table = page.getByRole("table", { name: "Harmonic evidence timeline" });
  await expect(table).toBeVisible();
  await expect(table.getByRole("columnheader")).toHaveText(["Time", "Chord", "Degree", "Function"]);
  await expect(table.locator(".inspector-harmony-row").filter({ hasNot: page.locator(".inspector-harmony-header") })).toHaveCount(6);

  // Key is already promoted once in Context. The compact degree column should
  // not repeat `(A minor)` on every row, while the original claim remains the
  // accessible label/title for provenance-oriented inspection.
  await expect(table).not.toContainText("(A minor)");
  await expect(table.getByRole("button", { name: "I (A minor)" }).first()).toBeVisible();
  await expect(table.getByText("Tonic", { exact: true }).first()).toBeVisible();

  const harmonyCount = harmonyDisclosure.locator(".inspector-evidence-count");
  await expect(harmonyCount).toHaveText("6");
});

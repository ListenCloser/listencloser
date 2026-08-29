import { expect, test, type Page } from "@playwright/test";

/**
 * Theory annotation E2E regression tests (MSW).
 *
 * Validates the Breakdown Inspector hierarchy:
 *   - Context shows interpretable Key, Tempo, Meter as quiet inline metadata
 *   - Evidence details stays secondary and does not expose raw category counts
 *   - Parallel chord / Roman numeral / function labels collapse into one harmonic moment
 *   - Clicking a harmonic moment sets a selection
 *   - Withheld capabilities (cadence, key_region) never appear
 */
test.describe("theory annotations (MSW)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(
      ({ projectRef, session }) => {
        try {
          window.localStorage.setItem(
            `sb-${projectRef}-auth-token`,
            JSON.stringify(session),
          );
        } catch {
          /* ignore */
        }
      },
      {
        projectRef: "cijhpddqvvzyzfzmkdnn",
        session: {
          access_token: "e2e-fake-access-token",
          token_type: "bearer",
          expires_in: 3600,
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          refresh_token: "e2e-fake-refresh-token",
          user: {
            id: "00000000-0000-0000-0000-000000000001",
            email: "e2e@example.com",
            aud: "authenticated",
            role: "authenticated",
            app_metadata: {},
            user_metadata: {},
            created_at: new Date().toISOString(),
          },
        },
      },
    );
    await page.goto("/");
    await page.waitForFunction(
      () => navigator.serviceWorker?.controller !== null,
      undefined,
      { timeout: 15_000 },
    );
  });

  async function openHarmonyEvidence(page: Page) {
    const evidenceRoot = page.locator("details.inspector-breakdown-evidence-root");
    await expect(evidenceRoot).toBeVisible();
    if ((await evidenceRoot.getAttribute("open")) === null) {
      await evidenceRoot.locator(":scope > summary").click();
    }
    await expect(evidenceRoot).toHaveAttribute("open", "");

    const harmony = evidenceRoot
      .locator("details.inspector-evidence-group")
      .filter({ hasText: /^Harmony/ })
      .first();
    await expect(harmony).toBeVisible();
    if ((await harmony.getAttribute("open")) === null) {
      await harmony.locator(":scope > summary").click();
    }
    await expect(harmony).toHaveAttribute("open", "");
    return { evidenceRoot, harmony };
  }

  test("Inspector shows interpretable Key, Tempo, Meter metadata", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    await expect(page.getByRole("tab", { name: "Breakdown", selected: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Context" })).toBeVisible();

    const metadata = page.getByRole("definition");
    await expect(page.getByText("Key", { exact: true })).toBeVisible();
    await expect(page.getByText("Tempo", { exact: true })).toBeVisible();
    await expect(page.getByText("Meter", { exact: true })).toBeVisible();

    await expect(page.getByText("A minor", { exact: true })).toBeVisible();
    await expect(page.getByText("112 BPM", { exact: true })).toBeVisible();
    await expect(page.getByText("4/4", { exact: true })).toBeVisible();
    await expect(metadata).toHaveCount(3);
  });

  test("Evidence details removes raw counts and collapses parallel harmony labels", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const { evidenceRoot, harmony } = await openHarmonyEvidence(page);
    const moments = harmony.locator(".inspector-harmony-moment");

    await expect(evidenceRoot.locator(":scope > summary")).toHaveText("Evidence details");
    await expect(harmony.locator(":scope > summary")).toHaveText("Harmony");
    await expect(moments).toHaveCount(6);
    await expect(moments.first()).toContainText("C maj");
    await expect(moments.first()).toContainText("I (A minor)");
    await expect(moments.first()).toContainText("TONIC (I)");

    await expect(harmony.getByRole("heading", { name: "Chords" })).toHaveCount(0);
    await expect(harmony.getByRole("heading", { name: "Roman numerals" })).toHaveCount(0);
    await expect(harmony.getByRole("heading", { name: "Function" })).toHaveCount(0);
  });

  test("all 6 chord labels remain visible in the collapsed harmony timeline", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const { harmony } = await openHarmonyEvidence(page);
    const moments = harmony.locator(".inspector-harmony-moment");
    await expect(moments).toHaveCount(6);

    await expect(moments.filter({ hasText: "C maj" }).first()).toBeVisible();
    await expect(moments.filter({ hasText: "G min" })).toBeVisible();
    await expect(moments.filter({ hasText: "F maj" })).toBeVisible();
    await expect(moments.filter({ hasText: "G7" })).toBeVisible();
  });

  test("Roman numeral context remains attached to the matching harmonic moments", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const { harmony } = await openHarmonyEvidence(page);
    const moments = harmony.locator(".inspector-harmony-moment");
    await expect(moments).toHaveCount(6);

    const cMajor = moments.filter({ has: page.locator(".inspector-harmony-primary", { hasText: "C maj" }) }).first();
    const gMinor = moments.filter({ has: page.locator(".inspector-harmony-primary", { hasText: "G min" }) }).first();
    const fMajor = moments.filter({ has: page.locator(".inspector-harmony-primary", { hasText: "F maj" }) }).first();
    const g7 = moments.filter({ has: page.locator(".inspector-harmony-primary", { hasText: "G7" }) }).first();

    await expect(cMajor.locator(".inspector-harmony-context")).toContainText("I (A minor)");
    await expect(gMinor.locator(".inspector-harmony-context")).toContainText("v (A minor)");
    await expect(fMajor.locator(".inspector-harmony-context")).toContainText("iv (A minor)");
    await expect(g7.locator(".inspector-harmony-context")).toContainText("V7 (A minor)");
  });

  test("Clicking a harmonic moment sets selection", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const { harmony } = await openHarmonyEvidence(page);
    const firstCMajor = harmony.locator(".inspector-harmony-moment").filter({ hasText: "C maj" }).first();
    await expect(firstCMajor).toBeVisible();
    await firstCMajor.click();

    await expect(page.locator(".inspector-scope-value")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("0:00–0:02")).toBeVisible();
  });

  test("no cadence or key_region insights appear", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    await openHarmonyEvidence(page);
    await expect(page.getByRole("heading", { name: "Cadences" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Key Regions" })).toHaveCount(0);
  });
});

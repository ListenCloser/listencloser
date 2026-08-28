import { expect, test, type Page } from "@playwright/test";

/**
 * Theory annotation E2E regression tests (MSW).
 *
 * Validates the Analysis Inspector hierarchy:
 *   - Overview shows interpretable Key, Tempo, Meter as quiet inline metadata
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
    const harmony = page
      .locator("details.inspector-evidence-group")
      .filter({ hasText: /^Harmony/ })
      .first();
    await expect(harmony).toBeVisible();
    if ((await harmony.getAttribute("open")) === null) {
      await harmony.locator("summary").click();
    }
    await expect(harmony).toHaveAttribute("open", "");
    return harmony;
  }

  test("Inspector shows interpretable Key, Tempo, Meter metadata", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    await expect(page.getByRole("tab", { name: "Analysis", selected: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

    const metadata = page.getByRole("definition");
    await expect(page.getByText("Key", { exact: true })).toBeVisible();
    await expect(page.getByText("Tempo", { exact: true })).toBeVisible();
    await expect(page.getByText("Meter", { exact: true })).toBeVisible();

    await expect(page.getByText("A minor", { exact: true })).toBeVisible();
    await expect(page.getByText("112 BPM", { exact: true })).toBeVisible();
    await expect(page.getByText("4/4", { exact: true })).toBeVisible();
    await expect(metadata).toHaveCount(3);
  });

  test("Inspector collapses chord, Roman numeral, and function into harmonic moments", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const moments = harmony.locator(".inspector-harmony-moment");

    await expect(moments).toHaveCount(6);
    await expect(moments.first()).toContainText("C maj");
    await expect(moments.first()).toContainText("I (A minor)");
    await expect(moments.first()).toContainText("TONIC (I)");

    await expect(harmony.getByRole("heading", { name: "Chords" })).toHaveCount(0);
    await expect(harmony.getByRole("heading", { name: "Roman numerals" })).toHaveCount(0);
    await expect(harmony.getByRole("heading", { name: "Function" })).toHaveCount(0);
  });

  test("all 6 chord labels remain visible in the collapsed harmony timeline", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const moments = harmony.locator(".inspector-harmony-moment");
    await expect(moments).toHaveCount(6);

    await expect(moments.filter({ hasText: "C maj" }).first()).toBeVisible();
    await expect(moments.filter({ hasText: "G min" })).toBeVisible();
    await expect(moments.filter({ hasText: "F maj" })).toBeVisible();
    await expect(moments.filter({ hasText: "G7" })).toBeVisible();
  });

  test("Roman numeral context remains attached to the matching harmonic moments", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const moments = harmony.locator(".inspector-harmony-moment");
    await expect(moments).toHaveCount(6);

    await expect(moments.filter({ hasText: "I (A minor)" }).first()).toBeVisible();
    await expect(moments.filter({ hasText: "v (A minor)" })).toBeVisible();
    await expect(moments.filter({ hasText: "iv (A minor)" })).toBeVisible();
    await expect(moments.filter({ hasText: "V7 (A minor)" })).toBeVisible();
  });

  test("Clicking a harmonic moment sets selection", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const firstCMajor = harmony.locator(".inspector-harmony-moment").filter({ hasText: "C maj" }).first();
    await expect(firstCMajor).toBeVisible();
    await firstCMajor.click();

    await expect(page.locator(".inspector-scope-value")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("0:00–0:02")).toBeVisible();
  });

  test("no cadence or key_region insights appear", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    await openHarmonyEvidence(page);
    await expect(page.getByRole("heading", { name: "Cadences" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Key Regions" })).toHaveCount(0);
  });
});
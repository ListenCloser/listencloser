import { expect, test, type Page } from "@playwright/test";

/**
 * Theory annotation E2E regression tests (MSW).
 *
 * Validates the Breakdown Inspector hierarchy:
 *   - Overview shows interpretable Key, Tempo, Meter as quiet inline metadata
 *   - Analysis opens once to one flat aligned harmonic timeline
 *   - Clicking chord / degree evidence sets a selection
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

  async function openHarmonyAnalysis(page: Page) {
    const analysisSummary = page.getByText("Analysis", { exact: true });
    await expect(analysisSummary).toBeVisible();
    await analysisSummary.click();

    const harmony = page.getByRole("region", { name: "Harmony analysis" });
    await expect(harmony).toBeVisible();
    return harmony;
  }

  test("Inspector shows interpretable Key, Tempo, Meter metadata", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    await expect(page.getByRole("tab", { name: "Breakdown", selected: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

    const metadata = page.getByRole("definition");
    await expect(page.getByText("Key", { exact: true })).toBeVisible();
    await expect(page.getByText("Tempo", { exact: true })).toBeVisible();
    await expect(page.getByText("Meter", { exact: true })).toBeVisible();

    await expect(page.getByText("A minor", { exact: true })).toBeVisible();
    await expect(page.getByText("112 BPM", { exact: true })).toBeVisible();
    await expect(page.getByText("4/4", { exact: true })).toBeVisible();
    await expect(metadata).toHaveCount(3);
    await expect(page.getByRole("heading", { name: "Context" })).toHaveCount(0);
  });

  test("Inspector shows one aligned harmony timeline", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyAnalysis(page);
    const table = harmony.getByRole("table", { name: "Harmonic analysis timeline" });

    await expect(table).toBeVisible();
    await expect(table.getByRole("columnheader")).toHaveText(["Time", "Harmony"]);
    await expect(table.getByRole("button", { name: "C maj", exact: true }).first()).toBeVisible();
    await expect(table.getByRole("button", { name: "I", exact: true }).first()).toBeVisible();
    await expect(table.getByRole("button", { name: "Tonic", exact: true }).first()).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Degree" })).toHaveCount(0);
    await expect(table.getByRole("columnheader", { name: "Function" })).toHaveCount(0);
  });

  test("all 6 chord entries rendered in the harmonic timeline", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyAnalysis(page);
    const table = harmony.getByRole("table", { name: "Harmonic analysis timeline" });

    await expect(table.getByRole("button", { name: "C maj", exact: true })).toHaveCount(3);
    await expect(table.getByRole("button", { name: "G min", exact: true })).toHaveCount(1);
    await expect(table.getByRole("button", { name: "F maj", exact: true })).toHaveCount(1);
    await expect(table.getByRole("button", { name: "G7", exact: true })).toHaveCount(1);
  });

  test("all 6 roman numeral entries remain accessible without repeating key text visibly", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyAnalysis(page);
    const table = harmony.getByRole("table", { name: "Harmonic analysis timeline" });

    await expect(table.getByRole("button", { name: "I", exact: true })).toHaveCount(3);
    await expect(table.getByRole("button", { name: "v", exact: true })).toHaveCount(1);
    await expect(table.getByRole("button", { name: "iv", exact: true })).toHaveCount(1);
    await expect(table.getByRole("button", { name: "V7", exact: true })).toHaveCount(1);
    await expect(table.getByRole("button").filter({ hasText: "(A minor)" })).toHaveCount(0);
    await expect(table.getByText("Evidence details", { exact: true })).toHaveCount(0);
  });

  test("Clicking a chord in Inspector sets selection", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyAnalysis(page);
    const table = harmony.getByRole("table", { name: "Harmonic analysis timeline" });

    await table.getByRole("button", { name: "C maj", exact: true }).first().click();

    await expect(page.locator(".inspector-scope-value")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("0:00–0:02")).toBeVisible();
  });

  test("no cadence or key_region insights appear", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    await openHarmonyAnalysis(page);
    await expect(page.getByRole("heading", { name: "Cadences" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Key Regions" })).toHaveCount(0);
  });
});
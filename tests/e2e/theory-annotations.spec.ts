import { expect, test, type Page } from "@playwright/test";

/**
 * Theory annotation E2E regression tests (MSW).
 *
 * Validates the Breakdown Inspector hierarchy:
 *   - Context shows interpretable Key, Tempo, Meter as quiet inline metadata
 *   - Evidence details can be expanded to one aligned harmonic timeline
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
    return harmony;
  }

  test("Inspector shows interpretable Key, Tempo, Meter metadata", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

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

  test("Inspector shows one aligned harmony timeline", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const table = harmony.getByRole("table", { name: "Harmonic evidence timeline" });

    await expect(table).toBeVisible();
    await expect(table.getByRole("columnheader")).toHaveText(["Time", "Chord", "Degree", "Function"]);
    await expect(table.getByRole("button", { name: "C maj" }).first()).toBeVisible();
    await expect(table.getByRole("button", { name: "I (A minor)" }).first()).toBeVisible();
    await expect(table.getByRole("button", { name: "TONIC (I)" }).first()).toBeVisible();
  });

  test("all 6 chord entries rendered in the harmonic timeline", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const table = harmony.getByRole("table", { name: "Harmonic evidence timeline" });

    await expect(table.getByRole("button", { name: "C maj" })).toHaveCount(3);
    await expect(table.getByRole("button", { name: "G min" })).toHaveCount(1);
    await expect(table.getByRole("button", { name: "F maj" })).toHaveCount(1);
    await expect(table.getByRole("button", { name: "G7" })).toHaveCount(1);
  });

  test("all 6 roman numeral entries remain accessible without repeating key text visibly", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const table = harmony.getByRole("table", { name: "Harmonic evidence timeline" });

    await expect(table.getByRole("button", { name: "I (A minor)" })).toHaveCount(3);
    await expect(table.getByRole("button", { name: "v (A minor)", exact: true })).toHaveCount(1);
    await expect(table.getByRole("button", { name: "iv (A minor)", exact: true })).toHaveCount(1);
    await expect(table.getByRole("button", { name: "V7 (A minor)" })).toHaveCount(1);
    await expect(table).not.toContainText("(A minor)");
  });

  test("Clicking a chord in Inspector sets selection", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const table = harmony.getByRole("table", { name: "Harmonic evidence timeline" });

    await table.getByRole("button", { name: "C maj" }).first().click();

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

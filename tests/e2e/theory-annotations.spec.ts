import { expect, test, type Page } from "@playwright/test";

/**
 * Theory annotation E2E regression tests (MSW).
 *
 * Validates the Breakdown Inspector hierarchy:
 *   - Context shows interpretable Key, Tempo, Meter as quiet inline metadata
 *   - Evidence details can be expanded to Harmony → Chords, Roman numerals, Function
 *   - Clicking a chord/RN sets a selection
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

  test("Inspector shows Harmony section with Chords, Roman numerals, Function sub-sections", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);

    await expect(harmony.getByRole("heading", { name: "Chords" })).toBeVisible();
    await expect(harmony.getByRole("button", { name: "C maj" }).first()).toBeVisible();

    await expect(harmony.getByRole("heading", { name: "Roman numerals" })).toBeVisible();
    await expect(harmony.getByRole("button", { name: "I (A minor)" }).first()).toBeVisible();

    await expect(harmony.getByRole("heading", { name: "Function" })).toBeVisible();
    await expect(harmony.getByRole("button", { name: "TONIC (I)" }).first()).toBeVisible();
  });

  test("all 6 chord entries rendered in Inspector", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    await expect(harmony.getByRole("heading", { name: "Chords" })).toBeVisible();

    await expect(harmony.getByRole("button", { name: "C maj" }).first()).toBeVisible();
    await expect(harmony.getByRole("button", { name: "G min" })).toBeVisible();
    await expect(harmony.getByRole("button", { name: "F maj" })).toBeVisible();
    await expect(harmony.getByRole("button", { name: "G7" })).toBeVisible();
  });

  test("all 6 roman numeral entries rendered in Inspector", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    await expect(harmony.getByRole("heading", { name: "Roman numerals" })).toBeVisible();

    await expect(harmony.getByRole("button", { name: "I (A minor)" }).first()).toBeVisible();
    await expect(harmony.getByRole("button", { name: "v (A minor)", exact: true })).toBeVisible();
    await expect(harmony.getByRole("button", { name: "iv (A minor)", exact: true })).toBeVisible();
    await expect(harmony.getByRole("button", { name: "V7 (A minor)" })).toBeVisible();
  });

  test("Clicking a chord in Inspector sets selection", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    await expect(harmony.getByRole("heading", { name: "Chords" })).toBeVisible();

    await harmony.getByRole("button", { name: "C maj" }).first().click();

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
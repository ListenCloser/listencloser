import { expect, test, type Page } from "@playwright/test";

/**
 * Theory annotation E2E regression tests (MSW).
 *
 * Validates the Breakdown Inspector hierarchy:
 *   - Context shows interpretable Key, Tempo, Meter as quiet inline metadata
 *   - Evidence details can be expanded to a compact time-aligned Harmony table
 *   - All admitted chord / degree / function source evidence remains present
 *   - Repeated key/numeral context is removed from the visible compact labels
 *   - Clicking harmonic evidence sets the same selection
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

  test("Inspector shows one aligned Harmony table without repeated visible context", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const timeline = harmony.getByRole("table", { name: "Harmonic timeline" });

    await expect(timeline).toBeVisible();
    await expect(timeline.getByRole("columnheader", { name: "Time" })).toBeVisible();
    await expect(timeline.getByRole("columnheader", { name: "Chord" })).toBeVisible();
    await expect(timeline.getByRole("columnheader", { name: "Degree" })).toBeVisible();
    await expect(timeline.getByRole("columnheader", { name: "Function" })).toBeVisible();
    await expect(timeline.getByRole("row")).toHaveCount(7); // header + six source moments

    await expect(timeline.getByRole("button", { name: /^Chord C maj at 0:00\./ })).toBeVisible();
    await expect(timeline.getByRole("button", { name: /^Degree I at 0:00\./ })).toBeVisible();
    await expect(timeline.getByRole("button", { name: /^Function Tonic at 0:00\./ })).toBeVisible();

    // Context owns the key once. The compact timeline should not print it six more times,
    // and Function should not repeat the already-adjacent degree in its visible label.
    await expect(timeline.getByText("A minor", { exact: true })).toHaveCount(0);
    await expect(timeline.getByText("TONIC (I)", { exact: true })).toHaveCount(0);
  });

  test("all 6 chord entries remain rendered in the compact Harmony timeline", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const chordButtons = harmony.getByRole("button", { name: /^Chord .+ at 0:/ });

    await expect(chordButtons).toHaveCount(6);
    await expect(harmony.getByRole("button", { name: /^Chord C maj at 0:00\./ })).toBeVisible();
    await expect(harmony.getByRole("button", { name: /^Chord G min at 0:02\./ })).toBeVisible();
    await expect(harmony.getByRole("button", { name: /^Chord F maj at 0:04\./ })).toBeVisible();
    await expect(harmony.getByRole("button", { name: /^Chord G7 at 0:08\./ })).toBeVisible();
  });

  test("all 6 Roman numeral entries remain rendered without repeated key suffixes", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    const degreeButtons = harmony.getByRole("button", { name: /^Degree .+ at 0:/ });

    await expect(degreeButtons).toHaveCount(6);
    await expect(harmony.getByRole("button", { name: /^Degree I at 0:00\./ })).toBeVisible();
    await expect(harmony.getByRole("button", { name: /^Degree v at 0:02\./ })).toBeVisible();
    await expect(harmony.getByRole("button", { name: /^Degree iv at 0:04\./ })).toBeVisible();
    await expect(harmony.getByRole("button", { name: /^Degree V7 at 0:08\./ })).toBeVisible();
    await expect(harmony.getByText(/\(A minor\)/)).toHaveCount(0);
  });

  test("Clicking a compact chord in Inspector sets selection", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    const harmony = await openHarmonyEvidence(page);
    await harmony.getByRole("button", { name: /^Chord C maj at 0:00\./ }).click();

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
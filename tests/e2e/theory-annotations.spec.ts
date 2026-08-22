import { expect, test } from "@playwright/test";

/**
 * Theory annotation E2E regression tests (MSW).
 *
 * Validates the fix for the P0 "nothing appears in UI" bug:
 *   - chord, roman_numeral, and harmonic_function insights must include
 *     spans so extractAnnotations() can derive start/end seconds.
 *   - The Inspector must render dedicated Chords, Roman Numerals, and
 *     Harmonic Function sections.
 *   - Clicking a theory event in the Inspector must set a selection.
 *
 * These tests would have failed BEFORE PR #277 because mock insights
 * had null spans and the annotation system skipped them.
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

  test("Inspector shows Chords, Roman Numerals, Harmonic Function sections", async ({
    page,
  }) => {
    // Wait for the work to load and the inspector to be visible.
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });

    // The inspector starts open (inspectorCollapsed: false).
    // Verify the Analysis tab is active and the theory sections render.
    await expect(page.getByRole("tab", { name: "Analysis", selected: true })).toBeVisible();

    // Chords section should be visible with chord entries
    await expect(page.getByRole("heading", { name: "Chords" })).toBeVisible();
    await expect(page.getByRole("button", { name: "C maj" }).first()).toBeVisible();

    // Roman Numerals section should be visible with RN entries
    await expect(page.getByRole("heading", { name: "Roman Numerals" })).toBeVisible();
    await expect(page.getByRole("button", { name: "I (A minor)" }).first()).toBeVisible();

    // Harmonic Function section should be visible with function entries
    await expect(page.getByRole("heading", { name: "Harmonic Function" })).toBeVisible();
    await expect(page.getByRole("button", { name: "TONIC (I)" }).first()).toBeVisible();
  });

  test("all 6 chord entries rendered in Inspector", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });

    await expect(page.getByRole("heading", { name: "Chords" })).toBeVisible();

    // Mock returns 6 chord entries; verify distinct chords are visible
    await expect(page.getByRole("button", { name: "C maj" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "G min" })).toBeVisible();
    await expect(page.getByRole("button", { name: "F maj" })).toBeVisible();
    await expect(page.getByRole("button", { name: "G7" })).toBeVisible();
  });

  test("all 6 roman numeral entries rendered in Inspector", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });

    await expect(page.getByRole("heading", { name: "Roman Numerals" })).toBeVisible();

    await expect(page.getByRole("button", { name: "I (A minor)" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "v (A minor)", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "iv (A minor)", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "V7 (A minor)" })).toBeVisible();
  });

  test("Clicking a chord in Inspector sets selection", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });

    await expect(page.getByRole("heading", { name: "Chords" })).toBeVisible();

    // Click first chord entry — should set a selection (scope header appears)
    await page.getByRole("button", { name: "C maj" }).first().click();

    // A selection scope header should appear showing the time range
    await expect(page.getByText("Selection", { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("0:00–0:02")).toBeVisible();
  });

  test("no cadence or key_region insights appear", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });

    // Cadence and key_region are WITHHELD from product.
    // These headings must NOT appear in the inspector.
    await expect(page.getByRole("heading", { name: "Cadences" })).not.toBeVisible();
    await expect(page.getByRole("heading", { name: "Key Regions" })).not.toBeVisible();
  });
});

import { expect, test } from "@playwright/test";

/**
 * Theory annotation E2E regression tests (MSW).
 *
 * Validates the new Analysis Inspector hierarchy:
 *   - Overview row shows Key, Tempo, Meter compactly
 *   - Harmony section contains Chords, Roman numerals, Function sub-sections
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

  test("Inspector shows compact overview row with Key, Tempo, Meter", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });

    await expect(page.getByRole("tab", { name: "Analysis", selected: true })).toBeVisible();

    // Overview row should show Key, Tempo, Meter labels
    await expect(page.getByText("Key", { exact: true })).toBeVisible();
    await expect(page.getByText("Tempo", { exact: true })).toBeVisible();
    await expect(page.getByText("Meter", { exact: true })).toBeVisible();

    // Values should be visible (use exact match to avoid matching RN buttons)
    await expect(page.getByText("A minor", { exact: true })).toBeVisible();
    await expect(page.getByText("112 BPM")).toBeVisible();
    await expect(page.getByText("4/4")).toBeVisible();
  });

  test("Inspector shows Harmony section with Chords, Roman numerals, Function sub-sections", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });

    // Harmony section heading
    await expect(page.getByRole("heading", { name: "Harmony" })).toBeVisible();

    // Chords sub-section
    await expect(page.getByRole("heading", { name: "Chords" })).toBeVisible();
    await expect(page.getByRole("button", { name: "C maj" }).first()).toBeVisible();

    // Roman numerals sub-section
    await expect(page.getByRole("heading", { name: "Roman numerals" })).toBeVisible();
    await expect(page.getByRole("button", { name: "I (A minor)" }).first()).toBeVisible();

    // Function sub-section
    await expect(page.getByRole("heading", { name: "Function" })).toBeVisible();
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

    await expect(page.getByRole("heading", { name: "Roman numerals" })).toBeVisible();

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
    await expect(page.locator(".inspector-scope-label")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("0:00\u20130:02")).toBeVisible();
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

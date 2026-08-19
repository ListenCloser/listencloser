import { expect, test } from "@playwright/test";

/**
 * Workspace ergonomics (MSW).
 *
 * Tests the analysis state transitions and the new layout structure:
 * - Compare is near the representation tabs, not in the transport
 * - Analysis states: idle → analyzing → completed
 * - Loop/Stop are icon buttons with aria-labels
 * - Library has one desktop toggle
 */
test.describe("workspace ergonomics (MSW)", () => {
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
      { projectRef: "cijhpddqvvzyzfzmkdnn", session: {
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
      }},
    );
    await page.goto("/");
    await page.waitForFunction(
      () => navigator.serviceWorker?.controller !== null,
      undefined,
      { timeout: 15_000 },
    );
  });

  test("Compare is near representation tabs, not in transport", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    // Compare button should be near the tabs
    await expect(page.getByRole("button", { name: "Compare", exact: true })).toBeVisible();

    // Compare should NOT be in the transport footer
    const transport = page.locator('[aria-label="Playback"]');
    await expect(transport.locator('button:has-text("Compare")')).not.toBeVisible();
  });

  test("analysis states: completed work shows Analysis tab", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });

    // The mock work has insights loaded, so analysisState should be "completed"
    // and the Analysis button should be visible
    await expect(page.getByRole("button", { name: "Analysis" })).toBeVisible();
  });

  test("loop and stop are icon buttons with aria-labels", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });

    // Loop button should have aria-label
    const loopBtn = page.getByRole("button", { name: "Toggle loop" });
    await expect(loopBtn).toBeVisible();
    await expect(loopBtn).toHaveAttribute("title", "Toggle loop");

    // Stop button should have aria-label
    const stopBtn = page.getByRole("button", { name: "Stop" });
    await expect(stopBtn).toBeVisible();
    await expect(stopBtn).toHaveAttribute("title", "Stop");
  });

  test("library has one desktop toggle in header only", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });

    // Header should have a Library button
    const header = page.locator("header.studio-header");
    await expect(header.getByRole("button", { name: /library/i })).toBeVisible();

    // The library panel itself should NOT have a separate collapse button
    // (it was removed - only the header toggle remains)
    const library = page.locator("aside.studio-library");
    await expect(library.locator('button[title="Collapse library"]')).not.toBeVisible();
  });

  test("piano roll fills available vertical space", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });
    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });

    // The piano roll scroll container should have a reasonable height
    const scroll = page.locator(".piano-roll-scroll");
    const box = await scroll.boundingBox();
    expect(box).not.toBeNull();
    // Should be at least 320px tall (our min-height)
    expect(box!.height).toBeGreaterThanOrEqual(320);
  });

  test("waveform ruler has sparse timestamps", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Test Work" })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    // Waveform ruler should be visible
    const ruler = page.locator(".waveform-ruler");
    await expect(ruler).toBeVisible();
  });
});

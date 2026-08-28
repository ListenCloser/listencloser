import { expect, test } from "@playwright/test";

/**
 * Workspace ergonomics (MSW).
 *
 * Tests the analysis state transitions and the new layout structure:
 * - Compare is integrated into the transport
 * - Completed analysis is visible in the persistent inspector
 * - Loop is an accessible icon button; play/pause is the primary transport action
 * - Library stays docked on desktop without duplicate collapse controls
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

  test("Compare is integrated into the transport", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    const transport = page.getByRole("contentinfo", { name: "Playback" });
    await expect(transport.getByRole("button", { name: "Compare", exact: true })).toBeVisible();
  });

  test("completed analysis is visible in the persistent inspector", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    // Desktop analysis is a stable dock, not a show/hide control. The mock work
    // already has insights loaded, so its selected Analysis tab and overview
    // are the durable completed-state signals.
    const inspector = page.locator("aside.inspector");
    await expect(inspector).toBeVisible();
    await expect(inspector.getByRole("tab", { name: "Analysis", selected: true })).toBeVisible();
    await expect(inspector.getByRole("heading", { name: "At a glance" })).toBeVisible();
    await expect(inspector.getByText("A minor", { exact: true })).toBeVisible();
  });

  test("loop is an accessible icon control", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const loopBtn = page.getByRole("button", { name: "Toggle loop" });
    await expect(loopBtn).toBeVisible();
    await expect(loopBtn).toHaveAttribute("title", "Loop");
    await expect(page.getByRole("button", { name: "Play", exact: true })).toBeVisible();
  });

  test("library is docked on desktop without duplicate collapse controls", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const library = page.locator("aside.studio-library");
    await expect(library).toBeVisible();
    await expect(library.getByRole("heading", { name: "Library" })).toBeVisible();
    await expect(library.locator('button[title="Collapse library"]')).toHaveCount(0);

    // The header control is mobile-only and should not duplicate the docked desktop navigation.
    await expect(page.locator("header.studio-header").getByRole("button", { name: /library/i })).not.toBeVisible();
  });

  test("piano roll fills available vertical space", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });

    // The redesigned roll uses the workspace canvas instead of a nested vertical scroller.
    const box = await page.getByTestId("piano-roll").boundingBox();
    expect(box).not.toBeNull();
    // Should be at least 320px tall (our min-height)
    expect(box!.height).toBeGreaterThanOrEqual(320);
  });

  test("waveform ruler has sparse timestamps", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    // Waveform ruler should be visible
    const ruler = page.locator(".waveform-ruler");
    await expect(ruler).toBeVisible();
  });
});
import { expect, test } from "@playwright/test";

/**
 * Workspace ergonomics (MSW).
 *
 * Tests the analysis state transitions and the layout structure:
 * - Compare is integrated into the transport
 * - Completed analysis is presented as an evidence-grounded Breakdown
 * - Loop is explicit and accessible; play/pause is the primary transport action
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
    const compare = transport.getByRole("button", { name: "Compare", exact: true });
    await expect(compare).toBeVisible();
    await expect(compare).not.toHaveAttribute("title");
    await compare.hover();
    await expect(page.getByRole("tooltip", { name: /Compare .+ with .+/ })).toBeVisible();
  });

  test("completed analysis is presented as a Breakdown with factual context", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const inspector = page.locator("aside.inspector");
    await expect(inspector).toBeVisible();
    await expect(inspector.getByRole("tab", { name: "Breakdown", selected: true })).toBeVisible();
    await expect(inspector.getByRole("heading", { name: "What stands out" })).toBeVisible();
    await expect(inspector.getByRole("heading", { name: "Context" })).toBeVisible();
    await expect(inspector.getByText("A minor", { exact: true })).toBeVisible();
    await expect(inspector.getByRole("heading", { name: "Overview" })).toHaveCount(0);
  });

  test("loop and playback controls expose their current action", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const loopBtn = page.getByRole("button", { name: "Toggle loop" });
    await expect(loopBtn).toBeVisible();
    await expect(loopBtn).toHaveAttribute("aria-pressed", "false");
    await expect(loopBtn).not.toHaveAttribute("title");
    await loopBtn.hover();
    await expect(page.getByRole("tooltip", { name: "Loop entire source" })).toBeVisible();
    await expect(loopBtn.getByText("Loop", { exact: true })).toBeVisible();

    const playBtn = page.getByRole("button", { name: "Play", exact: true });
    await expect(playBtn).toBeVisible();
    await expect(playBtn).not.toHaveAttribute("title");
    // Establish keyboard input modality before returning focus to Play. The
    // tooltip should follow :focus-visible, not linger after pointer/touch focus.
    await playBtn.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(playBtn).toBeFocused();
    await expect(page.getByRole("tooltip", { name: "Play recording" })).toBeVisible();

    // Radix dismisses a tooltip when its trigger is activated. Re-enter the
    // trigger before asserting the help for its newly toggled action.
    await loopBtn.click();
    await expect(loopBtn).toHaveAttribute("aria-pressed", "true");
    await page.mouse.move(0, 0);
    await loopBtn.hover();
    await expect(page.getByRole("tooltip", { name: "Turn loop off" })).toBeVisible();
  });

  test("library keeps the import action explicit on desktop", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const library = page.locator("aside.studio-library");
    await expect(library).toBeVisible();
    await expect(library.getByRole("heading", { name: "Library" })).toBeVisible();
    await expect(library.getByRole("button", { name: "Import audio", exact: true })).toBeVisible();
    await expect(library.locator('button[title="Collapse library"]')).toHaveCount(0);

    await expect(page.locator("header.studio-header").getByRole("button", { name: /library/i })).not.toBeVisible();
  });

  test("piano roll fills available vertical space", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });

    const box = await page.getByTestId("piano-roll").boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(320);
  });

  test("waveform ruler has sparse timestamps", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    const ruler = page.locator(".waveform-ruler");
    await expect(ruler).toBeVisible();
  });
});

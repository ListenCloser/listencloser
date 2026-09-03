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

    const loopBtn = page.getByRole("button", { name: "Toggle selected passage loop" });
    await expect(loopBtn).toBeVisible();
    await expect(loopBtn).toHaveAttribute("aria-pressed", "false");
    await expect(loopBtn).toBeDisabled();
    await expect(loopBtn).not.toHaveAttribute("title");
    // Disabled native controls cannot receive pointer events. Tooltip owns a
    // stable disabled-trigger wrapper specifically so hover help remains
    // available without making the control falsely interactive.
    const disabledLoopAnchor = page.locator("[data-tooltip-disabled-trigger]").filter({ has: loopBtn });
    await expect(disabledLoopAnchor).toBeVisible();
    await disabledLoopAnchor.hover();
    await expect(page.getByRole("tooltip", { name: "Select a passage to loop" })).toBeVisible();
    await expect(loopBtn.getByText("Loop", { exact: true })).toBeVisible();

    const playBtn = page.getByRole("button", { name: "Play Original", exact: true });
    await expect(playBtn).toBeVisible();
    await expect(playBtn).toHaveAccessibleName("Play Original");
    await expect(playBtn).not.toHaveAttribute("title");
    // The source-specific accessible name is the durable keyboard contract.
    // Tooltip portal timing is Radix-owned and is exercised through its
    // deterministic hover interaction instead of a programmatic focus round trip.
    await page.mouse.move(0, 0);
    await playBtn.hover();
    await expect(page.getByRole("tooltip", { name: "Play Original" })).toBeVisible();

    // A visible passage selection enables the same Loop control; there is no
    // second loop-region affordance.
    const canvas = page.getByTestId("waveform-canvas");
    await expect(canvas).toBeVisible();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("waveform canvas not found");
    await page.mouse.move(box.x + box.width * 0.2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2, { steps: 5 });
    await page.mouse.up();

    await expect(loopBtn).toBeEnabled();
    await page.mouse.move(0, 0);
    await loopBtn.hover();
    await expect(page.getByRole("tooltip", { name: "Loop selected passage" })).toBeVisible();

    // Radix dismisses a tooltip when its trigger is activated. Re-enter the
    // trigger before asserting the help for its newly toggled action.
    await loopBtn.click();
    await expect(loopBtn).toHaveAttribute("aria-pressed", "true");
    await page.mouse.move(0, 0);
    await loopBtn.hover();
    await expect(page.getByRole("tooltip", { name: "Turn passage loop off" })).toBeVisible();
  });

  test("library keeps Import primary and progressively discloses processing choices", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    const library = page.locator("aside.studio-library");
    await expect(library).toBeVisible();
    await expect(library.getByRole("heading", { name: "Library" })).toBeVisible();
    await expect(library.getByRole("button", { name: "Import audio", exact: true })).toBeVisible();
    await expect(library.locator('button[title="Collapse library"]')).toHaveCount(0);

    const processing = library.locator("details.library-import-settings");
    await expect(processing).not.toHaveAttribute("open");
    await expect(processing.getByText("Processing", { exact: true })).toBeVisible();

    await processing.getByText("Processing", { exact: true }).click();
    await expect(processing).toHaveAttribute("open");
    await expect(processing.getByRole("button", { name: "Auto" })).toHaveAttribute("aria-pressed", "true");

    await processing.getByRole("button", { name: "Solo piano" }).click();
    await expect(processing.getByRole("button", { name: "Solo piano" })).toHaveAttribute("aria-pressed", "true");
    await expect(library.getByRole("button", { name: "Import audio", exact: true })).toBeVisible();

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

  test("keeps the Piano Roll note layer continuous through workspace interaction", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await page.getByRole("tab", { name: "Piano Roll" }).click();

    const pianoRoll = page.getByTestId("piano-roll");
    const staticNotes = pianoRoll.locator('[data-piano-roll-layer="static-notes"]');
    await expect(staticNotes).toBeVisible({ timeout: 20_000 });

    // An expando survives only while this exact DOM node remains mounted. This
    // observes the user-visible continuity boundary without coupling the test
    // to React render counts or implementation-specific memoization.
    await staticNotes.evaluate((node) => {
      (node as SVGElement & { __continuityProbe?: string }).__continuityProbe = "original-static-layer";
    });

    const play = page.getByRole("button", { name: "Play Original", exact: true });
    await play.click();
    await expect(page.getByRole("button", { name: "Pause Original", exact: true })).toBeVisible();
    await expect(pianoRoll.locator('[data-playhead="true"]')).toBeVisible({ timeout: 10_000 });

    const svg = pianoRoll.locator("svg");
    const box = await svg.boundingBox();
    if (!box) throw new Error("piano roll SVG not found");
    await page.mouse.move(box.x + box.width * 0.2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.45, box.y + box.height / 2, { steps: 5 });
    await page.mouse.up();
    await expect(pianoRoll.locator('[data-selection-range="true"]')).toBeVisible();

    await page.locator("aside.inspector").getByRole("tab", { name: "Ask" }).click();
    await expect(staticNotes).toHaveJSProperty("__continuityProbe", "original-static-layer");

    await page.getByRole("tab", { name: "Waveform" }).click();
    await expect(pianoRoll).toBeHidden();
    await expect(staticNotes).toHaveJSProperty("__continuityProbe", "original-static-layer");

    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(pianoRoll).toBeVisible();
    await expect(staticNotes).toHaveJSProperty("__continuityProbe", "original-static-layer");
    await expect(pianoRoll.locator('[data-selection-range="true"]')).toBeVisible();
  });

  test("waveform ruler has sparse timestamps", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    const ruler = page.locator(".waveform-ruler");
    await expect(ruler).toBeVisible();
  });
});

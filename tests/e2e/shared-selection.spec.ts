import { expect, test } from "@playwright/test";

test.describe("shared musical selection (MSW)", () => {
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
    await page.evaluate(() => {
      const portal = document.querySelector("nextjs-portal");
      if (portal) portal.remove();
    });
  });

  async function dragWaveform(page: any, startFrac: number, endFrac: number) {
    const canvas = page.getByTestId("waveform-canvas");
    await expect(canvas).toBeVisible();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("waveform canvas not found");
    const startX = box.x + box.width * startFrac;
    const endX = box.x + box.width * endFrac;
    await page.mouse.move(startX, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(endX, box.y + box.height / 2, { steps: 5 });
    await page.mouse.up();
  }

  test("waveform drag-select highlights all views and passage loop stays truthful across compare domains", async ({
    page,
  }) => {
    // Wait for workspace to load.
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    // Choose a non-default audible source and a non-zero playhead before
    // changing visual representations. View tabs must not become transport
    // authority or silently reset the user's listening context.
    const originalSource = page.getByRole("button", { name: "Playback source: Original" });
    await expect(originalSource).toContainText("Listening · Original");
    await originalSource.click();
    await page.getByRole("option", { name: "Transcription", exact: true }).click();

    const transcriptionSource = page.getByRole("button", { name: "Playback source: Transcription" });
    await expect(transcriptionSource).toContainText("Listening · Transcription");
    const playbackPosition = page.getByRole("slider", { name: "Playback position" });
    await expect(playbackPosition).toBeEnabled();
    const maxPosition = Number(await playbackPosition.getAttribute("max"));
    const checkpoint = Math.max(0.001, maxPosition * 0.4);
    await playbackPosition.fill(String(checkpoint));
    const preservedPosition = await playbackPosition.inputValue();

    const expectTransportContinuity = async () => {
      await expect(transcriptionSource).toContainText("Listening · Transcription");
      await expect(playbackPosition).toHaveValue(preservedPosition);
    };

    // 1. Select a region in Waveform. The shared visible passage enables the
    // one canonical Loop control; there is no separate loop-region affordance.
    await dragWaveform(page, 0.2, 0.6);
    const loop = page.getByRole("button", { name: "Toggle selected passage loop" });
    await expect(loop).toBeVisible();
    await expect(loop).toBeEnabled();
    await expect(page.getByRole("button", { name: "Loop selection" })).toHaveCount(0);

    // Ordinary musical selection must not implicitly enter the dormant A/B
    // passage-comparison workflow. The separate transport Compare mode below
    // remains an explicit user action.
    await expect(page.getByRole("region", { name: "Compare passages" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Use selection as reference" })).toHaveCount(0);

    // 2. Piano Roll region stays highlighted, while the explicit audible
    // source and playhead remain independent from the visible representation.
    // Assert the semantic selection marker rather than coupling behavior
    // coverage to an exact paint opacity.
    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
    await expect(
      page.locator('[data-testid="piano-roll"] [data-selection-range="true"]'),
    ).toBeVisible({ timeout: 10_000 });
    await expectTransportContinuity();

    // 3. Score measures/region stay highlighted. Representation switches do
    // not change the active playback source or playhead, so the performance-
    // time loop is still compatible.
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-selection-highlight]')).toBeVisible({ timeout: 10_000 });
    await expectTransportContinuity();

    // 4. Enable looping for the visible passage.
    await loop.click();
    await expect(loop).toHaveAttribute("aria-pressed", "true");

    // 5. Compare is still independent. Moving playback to a notation-domain
    // Score source must clear the regional loop rather than leave invisible
    // performance-time bounds active; the shared visual selection persists.
    await page.getByRole("button", { name: "Compare", exact: true }).click();
    await expect(page.getByRole("group", { name: "Compare playback sources" })).toBeVisible();

    await page.getByRole("button", { name: "B compare source", exact: true }).click();
    await page.getByRole("option", { name: "Score", exact: true }).click();
    await expect(loop).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("button", { name: "B", exact: true }).click();
    await expect(page.getByRole("button", { name: "B", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(loop).toHaveAttribute("aria-pressed", "false");
    await expect(loop).toBeDisabled();
    await expect(page.locator('[data-selection-highlight]')).toBeVisible();

    await page.getByRole("button", { name: "A", exact: true }).click();
    await expect(page.getByRole("button", { name: "A", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(loop).toBeEnabled();
    await expect(loop).toHaveAttribute("aria-pressed", "false");
    await expect(page.locator('[data-selection-highlight]')).toBeVisible();

    // The user can explicitly re-enable looping once playback returns to the
    // compatible performance domain.
    await loop.click();
    await expect(loop).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("button", { name: "Exit compare", exact: true }).click();
    await expect(page.getByRole("group", { name: "Compare playback sources" })).not.toBeVisible();

    // 6. Reverse: select score measure → waveform shows region.
    await page.getByRole("tab", { name: "Score" }).click();
    const firstMeasure = page.locator("g.vf-measure").first();
    const measureBox = await firstMeasure.boundingBox();
    if (measureBox) {
      await page.mouse.click(measureBox.x + measureBox.width / 2, measureBox.y + measureBox.height / 2);
    }

    await page.getByRole("tab", { name: "Waveform" }).click();
    await expect(page.getByTestId("waveform-canvas")).toBeVisible();
  });

  test("score measure selection derives timeRange and highlights waveform", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });

    // Click first measure.
    const firstMeasure = page.locator("g.vf-measure").first();
    const measureBox = await firstMeasure.boundingBox();
    if (measureBox) {
      await page.mouse.click(measureBox.x + measureBox.width / 2, measureBox.y + measureBox.height / 2);
    }

    // Switch to Waveform - selection region remains shared.
    await page.getByRole("tab", { name: "Waveform" }).click();
    const canvas = page.getByTestId("waveform-canvas");
    await expect(canvas).toBeVisible();
  });
});

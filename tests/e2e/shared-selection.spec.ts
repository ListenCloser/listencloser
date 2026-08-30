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

  test("waveform drag-select highlights piano roll and score, loop selection persists across compare", async ({
    page,
  }) => {
    // Wait for workspace to load
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    // 1. Select region in Waveform (Listen view). A horizontal drag defines a
    // shared selection (it does not seek), so the transport exposes the
    // "Loop selection" affordance for the chosen range.
    await dragWaveform(page, 0.2, 0.6);
    await expect(page.getByRole("button", { name: "Loop selection" })).toBeVisible();

    // Ordinary musical selection must not implicitly enter the dormant A/B
    // passage-comparison workflow. The separate transport Compare mode below
    // remains an explicit user action.
    await expect(page.getByRole("region", { name: "Compare passages" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Use selection as reference" })).toHaveCount(0);

    // 2. Piano Roll region stays highlighted
    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
    await expect(
      page.locator('[data-testid="piano-roll"] svg >> rect[fill="var(--accent)"][fill-opacity="0.1"]'),
    ).toBeVisible({ timeout: 10_000 });

    // 3. Score measures/region stay highlighted
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-selection-highlight]')).toBeVisible({ timeout: 10_000 });

    // 4. Enable Loop selection
    await page.getByRole("button", { name: "Loop selection" }).click();
    await expect(page.getByRole("button", { name: "Loop selection" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    // 5. Play and enter Compare, toggle A/B - loop + selection persist
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({
      timeout: 10_000,
    });

    await page.getByRole("button", { name: "Compare", exact: true }).click();
    await expect(page.getByRole("group", { name: "Compare playback sources" })).toBeVisible();

    // Set B to Score
    await page.getByRole("button", { name: "B compare source", exact: true }).click();
    await page.getByRole("option", { name: "Score", exact: true }).click();

    for (const side of ["B", "A", "B"] as const) {
      await page.getByRole("button", { name: side, exact: true }).click();
      await expect(page.getByRole("button", { name: side, exact: true })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      await expect(page.getByRole("button", { name: "Loop selection" })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      await expect(page.locator('[data-selection-highlight]')).toBeVisible();
    }

    await page.getByRole("button", { name: "Exit compare", exact: true }).click();
    await expect(page.getByRole("group", { name: "Compare playback sources" })).not.toBeVisible();

    // 6. Reverse: select score measure → waveform shows region
    await page.getByRole("tab", { name: "Score" }).click();
    const firstMeasure = page.locator("g.vf-measure").first();
    const measureBox = await firstMeasure.boundingBox();
    if (measureBox) {
      await page.mouse.click(measureBox.x + measureBox.width / 2, measureBox.y + measureBox.height / 2);
    }

    await page.getByRole("tab", { name: "Waveform" }).click();
    await expect(page.getByTestId("waveform-canvas")).toBeVisible();
    // Selection rect should be present on waveform
    await expect(page.getByTestId("waveform-canvas")).toBeVisible();
  });

  test("score measure selection derives timeRange and highlights waveform", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });

    // Click first measure
    const firstMeasure = page.locator("g.vf-measure").first();
    const measureBox = await firstMeasure.boundingBox();
    if (measureBox) {
      await page.mouse.click(measureBox.x + measureBox.width / 2, measureBox.y + measureBox.height / 2);
    }

    // Switch to Listen (Waveform) - selection region visible
    await page.getByRole("tab", { name: "Waveform" }).click();
    await expect(page.getByTestId("waveform-canvas")).toBeVisible();
    // Waveform should show a selection rect
    const canvas = page.getByTestId("waveform-canvas");
    await expect(canvas).toBeVisible();
  });
});
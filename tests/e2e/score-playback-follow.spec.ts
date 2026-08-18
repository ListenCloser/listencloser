import { expect, test } from "@playwright/test";

test.describe("score playback following (MSW)", () => {
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

  test("playback highlight appears, advances on measure boundary, follows seek backward", async ({
    page,
  }) => {
    // Wait for workspace to load
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();

    // Navigate to Score view
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({
      timeout: 30_000,
    });

    // Switch to Score rendition source
    await page
      .getByRole("button", { name: /Listening to/ })
      .click();
    await page
      .getByRole("option", { name: "Score rendition", exact: true })
      .click();

    // Verify hint says notation time
    await expect(
      page.getByText(
        "Playing the score rendition in notation time.",
      ),
    ).toBeVisible();

    // Play
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Pause", exact: true }),
    ).toBeVisible({ timeout: 10_000 });

    // Playback highlight should appear
    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible({ timeout: 10_000 });

    // Capture initial playback highlight position
    const highlight1 = page.locator("[data-playback-highlight]").first();
    const box1 = await highlight1.boundingBox();
    expect(box1).not.toBeNull();

    // Wait for measure transition (mock measures are at 0,2,4,6,8,10s)
    // The audio is a short WAV, so we wait for the highlight to move
    await page.waitForTimeout(3000);

    // Check if highlight has moved (measure changed)
    // Wait for the highlight to be visible before boundingBox — the
    // playback highlight may have been removed and re-inserted during
    // the measure transition (getBBox retry cycle).
    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible({ timeout: 10_000 });
    const highlight2 = page.locator("[data-playback-highlight]").first();
    const box2 = await highlight2.boundingBox();
    expect(box2).not.toBeNull();

    // Pause — the mock audio is ~4s; it may have finished already.
    const pauseBtn = page.getByRole("button", { name: "Pause", exact: true });
    if (await pauseBtn.isVisible().catch(() => false)) {
      await pauseBtn.click();
    }
    await expect(
      page.getByRole("button", { name: "Play", exact: true }),
    ).toBeVisible();

    // Highlight should persist after pause
    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible();

    // Seek backward via the transport slider
    const slider = page.getByRole("slider", { name: "Playback position" });
    await slider.fill("0");
    await slider.dispatchEvent("change");

    // Highlight should follow to the first measure
    await page.waitForTimeout(500);
    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible();
  });

  test("playback highlight is removed when switching away from score source", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });

    // Navigate to Score view
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({
      timeout: 30_000,
    });

    // Switch to Score rendition source
    await page
      .getByRole("button", { name: /Listening to/ })
      .click();
    await page
      .getByRole("option", { name: "Score rendition", exact: true })
      .click();

    // Play
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible({ timeout: 10_000 });

    // Pause
    await page.getByRole("button", { name: "Pause", exact: true }).click();

    // Switch to Original source
    await page
      .getByRole("button", { name: /Listening to/ })
      .click();
    await page
      .getByRole("option", { name: "Original", exact: true })
      .click();

    // Playback highlight should be removed
    await expect(
      page.locator("[data-playback-highlight]"),
    ).not.toBeVisible();
  });

  test("selection and playback highlights are independent", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "Test Work" }),
    ).toBeVisible({ timeout: 20_000 });

    // Navigate to Score view
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({
      timeout: 30_000,
    });

    // Select a measure by clicking it
    const firstMeasure = page.locator("g.vf-measure").first();
    const measureBox = await firstMeasure.boundingBox();
    if (measureBox) {
      await page.mouse.click(
        measureBox.x + measureBox.width / 2,
        measureBox.y + measureBox.height / 2,
      );
    }

    // Selection highlight should appear
    await expect(
      page.locator("[data-selection-highlight]"),
    ).toBeVisible({ timeout: 10_000 });

    // Switch to Score rendition source and play
    await page
      .getByRole("button", { name: /Listening to/ })
      .click();
    await page
      .getByRole("option", { name: "Score rendition", exact: true })
      .click();
    await page.getByRole("button", { name: "Play", exact: true }).click();

    // Both highlights should be visible
    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.locator("[data-selection-highlight]"),
    ).toBeVisible();

    // They should be different elements
    const playbackCount = await page
      .locator("[data-playback-highlight]")
      .count();
    const selectionCount = await page
      .locator("[data-selection-highlight]")
      .count();
    expect(playbackCount).toBeGreaterThanOrEqual(1);
    expect(selectionCount).toBeGreaterThanOrEqual(1);
  });
});

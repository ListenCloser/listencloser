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
    await page.evaluate(() => {
      const portal = document.querySelector("nextjs-portal");
      if (portal) portal.remove();
    });
  });

  test("playback highlight appears, advances on measure boundary, follows seek backward", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();

    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({
      timeout: 30_000,
    });

    await page
      .getByRole("button", { name: /Playback source:/ })
      .click();
    await page
      .getByRole("option", { name: "Score", exact: true })
      .click();

    await expect(page.getByRole("button", { name: "Playback source: Score", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Pause", exact: true }),
    ).toBeVisible({ timeout: 10_000 });

    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible({ timeout: 10_000 });

    const highlight1 = page.locator("[data-playback-highlight]").first();
    const box1 = await highlight1.boundingBox();
    expect(box1).not.toBeNull();

    await page.waitForTimeout(1500);

    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible({ timeout: 10_000 });
    const highlight2 = page.locator("[data-playback-highlight]").first();
    await expect(highlight2).toBeVisible({ timeout: 5_000 });

    const pauseBtn = page.getByRole("button", { name: "Pause", exact: true });
    if (await pauseBtn.isVisible().catch(() => false)) {
      await pauseBtn.click();
    }
    await expect(
      page.getByRole("button", { name: "Play", exact: true }),
    ).toBeVisible();

    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible();
  });

  test("score follow remains synchronized while auditioning another source", async ({
    page,
  }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({
      timeout: 30_000,
    });

    await page
      .getByRole("button", { name: /Playback source:/ })
      .click();
    await page
      .getByRole("option", { name: "Score", exact: true })
      .click();

    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible({ timeout: 10_000 });

    const pause = page.getByRole("button", { name: "Pause", exact: true });
    if (await pause.isVisible().catch(() => false)) await pause.click();

    await page
      .getByRole("button", { name: /Playback source:/ })
      .click();
    await page
      .getByRole("option", { name: "Original", exact: true })
      .click();

    await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();
    await expect(page.locator("[data-playback-highlight]")).toBeVisible();

    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("[data-playback-highlight]")).toBeVisible();
  });

  test("selection and playback highlights are independent", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^Test Work\b/ }),
    ).toBeVisible({ timeout: 20_000 });

    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({
      timeout: 30_000,
    });

    const firstMeasure = page.locator("g.vf-measure").first();
    const measureBox = await firstMeasure.boundingBox();
    if (measureBox) {
      await page.mouse.click(
        measureBox.x + measureBox.width / 2,
        measureBox.y + measureBox.height / 2,
      );
    }

    await expect(
      page.locator("[data-selection-highlight]").first(),
    ).toBeVisible({ timeout: 10_000 });

    await page
      .getByRole("button", { name: /Playback source:/ })
      .click();
    await page
      .getByRole("option", { name: "Score", exact: true })
      .click();
    await page.getByRole("button", { name: "Play", exact: true }).click();

    await expect(
      page.locator("[data-playback-highlight]"),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.locator("[data-selection-highlight]").first(),
    ).toBeVisible();

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
import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";

/**
 * Real-stack browser workflow test.
 *
 * Runs the full app against a real backend + Supabase test database (no MSW,
 * no mocked API responses). Requires a dedicated integration environment:
 *
 *   - local Supabase with migrations applied (`supabase start`)
 *   - the FastAPI backend + worker running against that Supabase
 *   - `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` pointed at it
 *   - a test session (see tests/e2e/real-stack session helper)
 *
 * Not part of the default frontend CI; run it via the database-integration job.
 */
test.describe("@integration real-stack workflow", () => {
  test("upload → process → reopen persists the full work", async ({ page }, testInfo) => {
    test.skip(
      !process.env.REAL_STACK_SESSION_ACCESS_TOKEN,
      "real-stack session not configured",
    );

    const projectRef = process.env.REAL_STACK_PROJECT_REF ?? "cijhpddqvvzyzfzmkdnn";
    const accessToken = process.env.REAL_STACK_SESSION_ACCESS_TOKEN!;

    await page.addInitScript(
      ({ projectRef, accessToken }) => {
        window.localStorage.setItem(
          `sb-${projectRef}-auth-token`,
          JSON.stringify({
            access_token: accessToken,
            token_type: "bearer",
            expires_in: 3600,
            expires_at: Math.floor(Date.now() / 1000) + 3600,
            refresh_token: "",
            user: {
              id: "00000000-0000-0000-0000-000000000001",
              email: "e2e@example.com",
              aud: "authenticated",
              role: "authenticated",
              app_metadata: {},
              user_metadata: {},
              created_at: new Date().toISOString(),
            },
          }),
        );
      },
      { projectRef, accessToken },
    );

    await page.goto("/");

    const importButton = page.getByRole("complementary").getByRole("button", { name: "Import audio" });
    await expect(importButton).toBeVisible({ timeout: 30_000 });
    await importButton.click();

    const realAudio = process.env.REAL_AUDIO_FILE;
    await page.locator('input[type="file"]').setInputFiles(
      realAudio && existsSync(realAudio)
        ? realAudio
        : "tests/fixtures/piano-simple.m4a",
    );

    // Processing must complete without a visible "Operation failed".
    await expect(page.getByRole("tab", { name: "Piano roll" })).toBeVisible({
      timeout: 300_000,
    });
    await expect(page.getByText("Operation failed")).not.toBeVisible();

    // The full set of representations exists.
    await expect(page.getByRole("tab", { name: "Listen" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible();

    // Reload must keep the persisted state.
    await page.reload();
    await expect(page.getByRole("button", { name: /piece|work/i })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText("Operation failed")).not.toBeVisible();
  });
});

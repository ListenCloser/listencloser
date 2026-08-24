/**
 * Shared setup for real-stack E2E tests.
 *
 * Creates a single Supabase user, imports real-piano.m4a once, waits for the
 * full pipeline to complete, and provides the auth session to all tests.
 * This eliminates 3 redundant import+processing cycles (~15min savings).
 */

import { expect, type Page } from "@playwright/test";
import { existsSync } from "node:fs";

const REAL_AUDIO = process.env.REAL_AUDIO_FILE;
const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

export function storageKey(url: string): string {
  return `sb-${new URL(url).hostname.split(".")[0]}-auth-token`;
}

let cachedSession: Record<string, unknown> | null = null;

export async function createSession(): Promise<Record<string, unknown>> {
  if (cachedSession) return cachedSession;
  if (!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY) {
    throw new Error("SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY must be set");
  }
  const email = `real-stack-shared@real-stack.test`;
  const password = "real-stack-12345678";

  const created = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password, email_confirm: true }),
  });
  const createdBody = await created.json().catch(() => ({}));
  if (!created.ok && createdBody?.code !== "user_already_exists") {
    throw new Error(`failed to create test user: ${created.status} ${JSON.stringify(createdBody)}`);
  }

  const token = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const tokenBody = await token.json();
  if (!tokenBody?.access_token) {
    throw new Error(`failed to sign in test user: ${token.status} ${JSON.stringify(tokenBody)}`);
  }
  cachedSession = tokenBody;
  return tokenBody as Record<string, unknown>;
}

export async function injectAuth(page: Page) {
  const auth = await createSession();
  await page.addInitScript(
    ({ key, session }) => {
      window.localStorage.setItem(
        key,
        JSON.stringify({
          access_token: session.access_token,
          token_type: "bearer",
          expires_in: 3600,
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          refresh_token: session.refresh_token ?? "",
          user: session.user,
        }),
      );
    },
    { key: storageKey(SUPABASE_URL!), session: auth },
  );
}

export async function transportPosition(page: Page): Promise<number> {
  return Number(await page.getByRole("slider", { name: "Playback position" }).inputValue());
}

export async function expectPositionPreserved(
  page: Page,
  expected: number,
  tolerance = 0.25,
) {
  await expect
    .poll(
      async () => Math.abs((await transportPosition(page)) - expected) <= tolerance,
      { timeout: 10_000, message: `playhead must stay within ${tolerance}s of ${expected.toFixed(2)}s` },
    )
    .toBe(true);
}

export async function scoreCursorLeft(page: Page): Promise<string | null> {
  return page.evaluate(() => {
    const cursor = document.querySelector<HTMLElement>('.sheet-music-container img[id^="cursorImg"]');
    return cursor ? cursor.style.left : null;
  });
}

export async function openSourceSelector(page: Page) {
  await page.getByRole("button", { name: /Listening to:/ }).click();
}

export async function selectSource(page: Page, label: string) {
  await openSourceSelector(page);
  await page.getByRole("option", { name: label, exact: true }).click();
}

export async function listeningTo(page: Page, label: string) {
  return page.getByRole("button", { name: `Listening to: ${label}`, exact: true });
}

export async function setCompareSideSource(page: Page, side: "A" | "B", label: string) {
  await page.getByRole("button", { name: new RegExp(`^${side}: `) }).click();
  await page.getByRole("option", { name: label, exact: true }).click();
}

export async function waitForProjectReady(page: Page) {
  await page
    .waitForResponse(
      (resp) =>
        /\/api\/v1\/projects\/[^/]+\/works$/.test(new URL(resp.url()).pathname) &&
        resp.request().method() === "GET",
      { timeout: 30_000 },
    )
    .catch(() => {});
  await expect(
    page.getByRole("complementary").getByRole("button", { name: "Import audio" }),
  ).toBeEnabled({ timeout: 30_000 });
}

export async function importWithRetry(page: Page) {
  await waitForProjectReady(page);
  for (let attempt = 0; attempt < 5; attempt++) {
    const importButton = page
      .getByRole("complementary")
      .getByRole("button", { name: "Import audio" });
    await expect(importButton).toBeEnabled({ timeout: 30_000 });
    await importButton.click();
    await page.locator('input[type="file"]').setInputFiles(REAL_AUDIO!);

    const uploading = page.getByText("Uploading your recording…");
    const failed = page.getByRole("alert").filter({ hasText: "Your project is still loading" });
    const outcome = await Promise.race([
      uploading.waitFor({ state: "visible", timeout: 15_000 }).then(() => "started"),
      failed.waitFor({ state: "visible", timeout: 15_000 }).then(() => "failed"),
    ]);
    if (outcome === "started") return;
    await failed.getByRole("button", { name: "Try another file" }).click();
    await expect(failed).toBeHidden({ timeout: 10_000 });
  }
  throw new Error("import did not start after retries");
}

/**
 * Import audio and wait for the full pipeline to complete.
 * Returns the page ready for testing.
 */
export async function importAndWaitForProcessing(page: Page) {
  await page.goto("/");
  await importWithRetry(page);
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 300_000 });
  await expect(page.getByText("Operation failed")).not.toBeVisible();
  await expect(page.getByText(/APIError|not-null|constraint|Postgres/i)).not.toBeVisible();
}

export function skipIfNoEnv() {
  if (!REAL_AUDIO || !existsSync(REAL_AUDIO)) return true;
  if (!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY) return true;
  return false;
}

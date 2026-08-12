import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";

/**
 * Real-stack browser workflow test (tagged `@integration`).
 *
 * Exercises the actual product happy path against a real backend + worker +
 * local Supabase — no MSW, no mocked API responses. The stack is started by the
 * `real-stack-e2e` CI job; this file only drives the browser.
 *
 * Required environment:
 *   REAL_AUDIO_FILE              absolute path to the canonical audio fixture
 *   SUPABASE_URL                 local Supabase URL (e.g. http://127.0.0.1:54321)
 *   SUPABASE_ANON_KEY            local Supabase anon key
 *   SUPABASE_SERVICE_ROLE_KEY    local Supabase service-role key
 *
 * Score *playback* (Score source, cursor following, click-to-seek) is the scope
 * of PR #207 and is intentionally not asserted here; this suite verifies that
 * the Score *notation* renders and that Original/Transcription playback work.
 */

const REAL_AUDIO = process.env.REAL_AUDIO_FILE;
const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

function storageKey(url: string): string {
  // Mirrors @supabase/supabase-js default storage key derivation.
  return `sb-${new URL(url).hostname.split(".")[0]}-auth-token`;
}

let session: Record<string, unknown> | null = null;

async function createSession(): Promise<Record<string, unknown>> {
  if (session) return session;
  if (!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY) {
    throw new Error("SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY must be set");
  }
  const email = `e2e-${Date.now()}@real-stack.test`;
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
  session = tokenBody;
  return tokenBody as Record<string, unknown>;
}

async function transportPosition(page: import("@playwright/test").Page): Promise<number> {
  return Number(await page.getByRole("slider", { name: "Playback position" }).inputValue());
}

test("real-stack happy path: import → play → inspect → reload → delete", async ({ page }) => {
  test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required for the canonical real-stack test (no fallback fixture)");
  test.skip(!existsSync(REAL_AUDIO!), `REAL_AUDIO_FILE does not exist: ${REAL_AUDIO}`);
  test.skip(!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY, "local Supabase env not configured");

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

  // ── Wait for the app to finish first-load project setup ─────────────────────
  // The app lazily creates the project on first load; importing before that
  // completes races with `projectId` and surfaces "Your project is still
  // loading". Wait for the create/list round-trip to settle first.
  const projectSettled = page.waitForResponse(
    (resp) => resp.url().includes("/api/v1/projects") && resp.request().method() === "POST",
    { timeout: 30_000 },
  ).catch(() => {});
  await page.goto("/");
  await projectSettled;

  // ── Import real audio ──────────────────────────────────────────────────────
  const importButton = page.getByRole("complementary").getByRole("button", { name: "Import audio" });
  await expect(importButton).toBeVisible({ timeout: 30_000 });
  await importButton.click();
  await page.locator('input[type="file"]').setInputFiles(REAL_AUDIO!);

  // ── Processing completes with no raw error surfaced ────────────────────────
  await expect(page.getByRole("tab", { name: "Piano roll" })).toBeVisible({ timeout: 300_000 });
  await expect(page.getByText("Operation failed")).not.toBeVisible();
  await expect(page.getByText(/APIError|not-null|constraint|Postgres/i)).not.toBeVisible();

  // ── Original audio plays and transport advances ────────────────────────────
  await page.getByRole("button", { name: "Original", exact: true }).click();
  await expect(page.getByRole("button", { name: "Original", exact: true })).toHaveAttribute("aria-pressed", "true");
  const originalStart = await transportPosition(page);
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect.poll(() => transportPosition(page), { timeout: 15_000 }).toBeGreaterThan(originalStart);
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // ── Transcription is a distinct source and also plays ──────────────────────
  await page.getByRole("button", { name: "Transcription", exact: true }).click();
  await expect(page.getByRole("button", { name: "Transcription", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Original", exact: true })).toHaveAttribute("aria-pressed", "false");
  const transcriptionStart = await transportPosition(page);
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect.poll(() => transportPosition(page), { timeout: 15_000 }).toBeGreaterThan(transcriptionStart);
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // ── Piano roll renders notes ───────────────────────────────────────────────
  await page.getByRole("tab", { name: "Piano roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/\d+ notes/)).toBeVisible();

  // ── Score notation renders ─────────────────────────────────────────────────
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });

  // ── Analysis persists real insight content ─────────────────────────────────
  await page.getByRole("tab", { name: "Analysis" }).click();
  await expect(page.getByText(/Key|Tempo|BPM|Time signature/i).first()).toBeVisible({ timeout: 20_000 });

  // ── Reload keeps persisted state ───────────────────────────────────────────
  await page.reload();
  await expect(page.getByRole("tab", { name: "Listen" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("tab", { name: "Piano roll" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Original", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Transcription", exact: true })).toBeVisible();

  // ── Switch sources again after reload ──────────────────────────────────────
  await page.getByRole("button", { name: "Original", exact: true }).click();
  await expect(page.getByRole("button", { name: "Original", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Transcription", exact: true }).click();
  await expect(page.getByRole("button", { name: "Transcription", exact: true })).toHaveAttribute("aria-pressed", "true");

  // ── Delete is durable across reload ────────────────────────────────────────
  await page.getByTitle("Delete work").click();
  await page.getByTitle("Click again to confirm delete").click();
  await expect(page.getByText(/Imported works will appear here|Start with a recording/i)).toBeVisible({ timeout: 15_000 });

  await page.reload();
  await expect(page.getByRole("tab", { name: "Listen" })).not.toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Start with a recording/i)).toBeVisible({ timeout: 30_000 });
});

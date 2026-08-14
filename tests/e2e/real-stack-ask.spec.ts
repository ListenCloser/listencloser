import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";

/**
 * Real-stack Ask inspector test (tagged `@integration`).
 *
 * Exercises the contextual Ask inspector against the real backend + worker +
 * local Supabase (no MSW). The stack is started by the `real-stack-e2e` CI
 * job; this file only drives the browser.
 *
 * The Ask endpoint does not exist on the backend yet, so ONLY the ask network
 * call is mocked via page.route — everything else (works, versions, entities,
 * insights, playback) runs against the real stack. This proves the Ask UI is
 * a real frontend surface over the real workspace, not a mock-only affordance.
 *
 * Required environment:
 *   REAL_AUDIO_FILE              absolute path to the canonical audio fixture
 *   SUPABASE_URL                 local Supabase URL (e.g. http://127.0.0.1:54321)
 *   SUPABASE_ANON_KEY            local Supabase anon key
 *   SUPABASE_SERVICE_ROLE_KEY    local Supabase service-role key
 *
 * Screenshots are written to docs/pr/<PR>/ and prove the Ask inspector renders
 * real workspace states (empty, selection-scoped, answered, error).
 */

const REAL_AUDIO = process.env.REAL_AUDIO_FILE;
const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

const SHOTS = process.env.SCREENSHOT_DIR ?? "docs/pr/227";

function storageKey(url: string): string {
  return `sb-${new URL(url).hostname.split(".")[0]}-auth-token`;
}

let session: Record<string, unknown> | null = null;
let failAsk = false;

async function createSession(): Promise<Record<string, unknown>> {
  if (session) return session;
  if (!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY) {
    throw new Error("SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY must be set");
  }
  const email = `ask-ui-${Date.now()}@real-stack.test`;
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

async function injectAuth(page: import("@playwright/test").Page) {
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

async function transportPosition(page: import("@playwright/test").Page): Promise<number> {
  return Number(await page.getByRole("slider", { name: "Playback position" }).inputValue());
}

async function selectSource(page: import("@playwright/test").Page, label: string) {
  await page.getByRole("button", { name: /Listening to:/ }).click();
  await page.getByRole("option", { name: label, exact: true }).click();
}

async function waitForProjectReady(page: import("@playwright/test").Page) {
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

async function importWithRetry(page: import("@playwright/test").Page) {
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

test.describe("contextual Ask inspector (real stack)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required (no fallback fixture)");
    test.skip(!existsSync(REAL_AUDIO!), `REAL_AUDIO_FILE does not exist: ${REAL_AUDIO}`);
    test.skip(!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY, "local Supabase env not configured");
    await injectAuth(page);
    // Only the Ask endpoint is mocked; the rest of the stack is real. The
    // handler is switchable so the test can also capture the error state.
    failAsk = false;
    await page.route("**/api/v1/ask", (route) => {
      if (failAsk) {
        route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ error: "Ask is unavailable" }),
        });
        return;
      }
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          answer: "This passage stays on the tonic with a gentle stepwise descent.",
          references: [
            { type: "time", start: 2, end: 6, domain: "performance" },
            { type: "measure", start: 1, end: 3 },
          ],
          suggestedActions: [
            { type: "show_representation", representationId: "score" },
            { type: "loop", start: 2, end: 6, domain: "performance" },
            { type: "seek", seconds: 2, domain: "performance" },
          ],
        }),
      });
    });
  });

  test("Ask inspects the real workspace: open → answer → switch modes → collapse", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");

    await importWithRetry(page);
    await expect(page.getByRole("tab", { name: "Piano roll" })).toBeVisible({ timeout: 300_000 });
    await expect(page.getByText("Operation failed")).not.toBeVisible();

    // ── 1. Ask empty state over the whole piece ────────────────────────────
    await page.getByRole("tab", { name: "Ask" }).click();
    await expect(page.getByPlaceholder("Ask about this piece…")).toBeVisible();
    await expect(page.getByText("Whole piece")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/ask-01-whole-piece.png` });

    // ── 2. Ask empty state scoped to a selection ───────────────────────────
    await page.getByRole("tab", { name: "Listen" }).click();
    const canvas = page.getByTestId("waveform-canvas");
    await expect(canvas).toBeVisible();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("waveform canvas not found");
    await page.mouse.move(box.x + box.width * 0.2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2, { steps: 5 });
    await page.mouse.up();
    await page.getByRole("tab", { name: "Ask" }).click();
    await expect(page.locator(".ask-context-value")).not.toHaveText("Whole piece");
    await page.screenshot({ path: `${SHOTS}/ask-02-selection-empty.png` });

    // ── Playback continues through the mode switch (never stopped) ────────
    await selectSource(page, "Original");
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
    const posPlaying = await transportPosition(page);
    await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThanOrEqual(posPlaying);

    // Analysis ↔ Ask preserves playback: still playing, still advancing.
    await page.getByRole("tab", { name: "Analysis" }).click();
    await expect(page.getByRole("heading", { name: "Analysis" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
    const posInAnalysis = await transportPosition(page);
    await page.getByRole("tab", { name: "Ask" }).click();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
    await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThanOrEqual(posInAnalysis);
    await page.getByRole("button", { name: "Pause", exact: true }).click();

    // ── 3. Ask an actual question → answer with evidence references ────────
    await page.getByRole("button", { name: "What is happening harmonically here?" }).click();
    await expect(page.getByText("What is happening harmonically here?")).toBeVisible();
    await expect(page.getByText(/This passage stays on the tonic/)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Evidence")).toBeVisible();
    await expect(page.getByText("0:02–0:06")).toBeVisible();
    await expect(page.getByText("Measures 1–3")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/ask-03-answer-references.png` });

    // ── 4. Suggested actions render as chips ───────────────────────────────
    await expect(page.getByRole("button", { name: "Open Score" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Loop passage" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Jump to time" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/ask-04-answer-actions.png` });

    // ── 5. Error state: a failed ask shows an inline retryable error ───────
    failAsk = true;
    await page.getByPlaceholder("Ask about this piece…").fill("What key is this passage in?");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.getByText(/not available right now/)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/ask-05-error.png` });
    failAsk = false;

    // ── Representation/transport state stays intact after Ask ──────────────
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Ask" }).click();
    await expect(page.getByText(/This passage stays on the tonic/)).toBeVisible();

    // ── Collapse/reopen preserves the Ask conversation ─────────────────────
    await page.getByRole("button", { name: "Hide analysis" }).click();
    await expect(page.locator(".inspector")).toHaveCount(0);
    await page.getByRole("button", { name: "Show analysis" }).click();
    await expect(page.locator(".inspector")).toBeVisible();
    await expect(page.getByText(/This passage stays on the tonic/)).toBeVisible();

    // ── 6. Narrow width: the Ask drawer renders with a backdrop ────────────
    await page.setViewportSize({ width: 768, height: 900 });
    await expect(page.locator(".studio-inspector-backdrop")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/This passage stays on the tonic/)).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/ask-06-narrow-drawer.png` });
  });
});
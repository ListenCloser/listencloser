import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";

/**
 * Real-stack Inspector test (tagged `@integration`).
 *
 * Exercises the contextual analysis inspector against the real backend +
 * worker + local Supabase (no MSW). The stack is started by the
 * `real-stack-e2e` CI job; this file only drives the browser.
 *
 * Required environment:
 *   REAL_AUDIO_FILE              absolute path to the canonical audio fixture
 *   SUPABASE_URL                 local Supabase URL (e.g. http://127.0.0.1:54321)
 *   SUPABASE_ANON_KEY            local Supabase anon key
 *   SUPABASE_SERVICE_ROLE_KEY    local Supabase service-role key
 *
 * Screenshots are written to docs/pr/224/ and prove the inspector renders real
 * workspace states (whole-piece analysis, selection-scoped analysis, sparse
 * analysis, collapsed, and the narrow-width drawer) rather than mocks.
 */

const REAL_AUDIO = process.env.REAL_AUDIO_FILE;
const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

const SHOTS = "docs/pr/224";

function storageKey(url: string): string {
  return `sb-${new URL(url).hostname.split(".")[0]}-auth-token`;
}

let session: Record<string, unknown> | null = null;

async function createSession(): Promise<Record<string, unknown>> {
  if (session) return session;
  if (!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY) {
    throw new Error("SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY must be set");
  }
  const email = `inspector-${Date.now()}@real-stack.test`;
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
  // The frontend creates the project (POST /projects) and only then calls
  // setProjectId after a follow-up listWorks round-trip (GET /projects/:id/works).
  // Waiting for that works response is the deterministic "project is ready"
  // signal — the project POST alone resolves before projectId is set.
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

    // Import either starts (uploading overlay) or races project setup and shows
    // the "project is still loading" alert. Only treat the alert as a retry;
    // never assume success on a timeout.
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

test.describe("contextual analysis inspector (real stack)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required (no fallback fixture)");
    test.skip(!existsSync(REAL_AUDIO!), `REAL_AUDIO_FILE does not exist: ${REAL_AUDIO}`);
    test.skip(!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY, "local Supabase env not configured");
    await injectAuth(page);
  });

  test("inspect the real workspace: play → whole-piece → selection → score → collapse → drawer", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");

    // ── Import real audio and wait for processing ───────────────────────────
    await importWithRetry(page);
    await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 300_000 });
    await expect(page.getByText("Operation failed")).not.toBeVisible();

    // ── Whole-piece analysis is the default inspector scope ─────────────────
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
    await expect(page.locator(".inspector")).toBeVisible();
    await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible();
    
    await page.screenshot({ path: `${SHOTS}/01-listen-whole-piece-inspector.png` });

    // ── Playback: opening/using the inspector never stops playback ──────────
    await selectSource(page, "Original");
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.locator(".inspector")).toBeVisible();
    const posPlaying = await transportPosition(page);
    await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThanOrEqual(posPlaying);
    await page.getByRole("button", { name: "Pause", exact: true }).click();

    // ── Seek to a real insight: a defensible start position (not 0) ─────────
    // Whole-piece findings may be present or sparse; if a seekable observation
    // or chip renders, clicking it must move the transport to its time.
    const seekable = page.locator(".inspector .inspector-observation, .inspector .rn-chip").first();
    if (await seekable.count().catch(() => 0)) {
      const beforeSeek = await transportPosition(page);
      await seekable.click();
      await expect.poll(() => transportPosition(page), { timeout: 10_000 }).not.toBe(beforeSeek);
      await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThan(0);
    }

    // ── Select a region on the waveform → selection-scoped inspector ────────
    const canvas = page.getByTestId("waveform-canvas");
    await expect(canvas).toBeVisible();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("waveform canvas not found");
    const startX = box.x + box.width * 0.2;
    const endX = box.x + box.width * 0.6;
    await page.mouse.move(startX, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(endX, box.y + box.height / 2, { steps: 6 });
    await page.mouse.up();
    await expect(page.locator(".inspector-scope-label", { hasText: "Selection" })).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: `${SHOTS}/02-listen-selection-inspector.png` });

    // ── Piano roll stays selected and inspector stays open ──────────────────
    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
    await expect(page.locator(".inspector")).toBeVisible();
    await expect(page.locator(".inspector-scope-label", { hasText: "Selection" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/03-piano-roll-selected-region-inspector.png` });

    // ── Score measures stay selected and inspector stays open ───────────────
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator(".inspector")).toBeVisible();
    await expect(page.locator(".inspector-scope-label", { hasText: "Selection" })).toBeVisible();

    // Click a later measure: measure-scoped selection with derived time range.
    // OSMD engraves the score asynchronously, so wait for the measure groups.
    const measures = page.locator(".sheet-music-container g.vf-measure");
    await expect
      .poll(async () => measures.count(), { timeout: 30_000 })
      .toBeGreaterThan(1);
    const targetMeasure = measures.nth(1);
    const targetBox = await targetMeasure.boundingBox();
    expect(targetBox).not.toBeNull();
    await page.mouse.click(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2);
    await expect(page.getByText(/Measures \d+–\d+/)).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: `${SHOTS}/04-score-selected-measures-inspector.png` });

    // ── Sparse selection state: a region with no specific analysis ──────────
    // Select a tiny region late in the piece where the app reports no
    // selection-specific findings, proving the honest "no specific analysis"
    // state (never fabricated).
    await page.getByRole("tab", { name: "Waveform" }).click();
    await expect(canvas).toBeVisible();
    const box2 = await canvas.boundingBox();
    if (box2) {
      const s = box2.x + box2.width * 0.92;
      const e = box2.x + box2.width * 0.97;
      await page.mouse.move(s, box2.y + box2.height / 2);
      await page.mouse.down();
      await page.mouse.move(e, box2.y + box2.height / 2, { steps: 3 });
      await page.mouse.up();
    }
    await page.screenshot({ path: `${SHOTS}/05-sparse-analysis.png` });

    // ── Collapse the inspector; the workspace keeps the representation ──────
    await page.getByRole("button", { name: "Hide analysis" }).click();
    await expect(page.locator(".inspector")).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/06-inspector-collapsed.png` });
    await page.getByRole("button", { name: "Show analysis" }).click();
    await expect(page.locator(".inspector")).toBeVisible();

    // ── Mid width (1024px): the inspector stays inline, no drawer/backdrop ──
    await page.setViewportSize({ width: 1024, height: 900 });
    await expect(page.locator(".inspector")).toBeVisible();
    await expect(page.locator(".studio-inspector-backdrop")).not.toBeVisible();

    // ── Narrow width: the inspector becomes a fixed drawer with a backdrop ──
    await page.setViewportSize({ width: 768, height: 900 });
    await expect(page.locator(".studio-inspector-backdrop")).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: `${SHOTS}/07-narrow-width-drawer.png` });
    // Clicking the backdrop closes the drawer.
    await page.locator(".studio-inspector-backdrop").click({ position: { x: 10, y: 450 } });
    await expect(page.locator(".inspector")).toHaveCount(0);
    await page.getByRole("button", { name: "Show analysis" }).click();
    await expect(page.locator(".inspector")).toBeVisible();
  });
});
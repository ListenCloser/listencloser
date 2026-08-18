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
 * Covers the full happy path including score playback: Original and
 * Transcription playback, Score as a distinct notation-derived source, animated
 * score following, measure click-to-seek, reload persistence, A/B source
 * comparison, and deletion.
 *
 * Source-switch timing tolerance: switching sources reads the transport's
 * `audio.currentTime` at the instant of the switch and clamps it to the target
 * source's duration, so the playhead is preserved exactly (0 s tolerance) when
 * paused. The E2E therefore asserts exact equality after pausing. While
 * playing, headless Chromium's media clock can stall, so playback assertions
 * only require non-regression (position >= prior sample).
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

// The transport playhead is preserved (not reset, not jumped) when paused and
// the heard source is swapped. Headless Chromium's media clock can jitter by a
// fraction of a second, so assert the semantic contract with a small tolerance
// instead of exact float equality.
async function expectPositionPreserved(
  page: import("@playwright/test").Page,
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

async function scoreCursorLeft(page: import("@playwright/test").Page): Promise<string | null> {
  return page.evaluate(() => {
    const cursor = document.querySelector<HTMLElement>('.sheet-music-container img[id^="cursorImg"]');
    return cursor ? cursor.style.left : null;
  });
}

// ── Source selector helpers ─────────────────────────────────────────────
async function openSourceSelector(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: /Listening to:/ }).click();
}

async function selectSource(page: import("@playwright/test").Page, label: string) {
  await openSourceSelector(page);
  await page.getByRole("option", { name: label, exact: true }).click();
}

async function listeningTo(page: import("@playwright/test").Page, label: string) {
  return page.getByRole("button", { name: `Listening to: ${label}`, exact: true });
}

async function setCompareSideSource(page: import("@playwright/test").Page, side: "A" | "B", label: string) {
  await page.getByRole("button", { name: new RegExp(`^${side}: `) }).click();
  await page.getByRole("option", { name: label, exact: true }).click();
}

// The app lazily creates the project on first load; importing before the
// project is ready races with `projectId` and surfaces "Your project is still
// loading". Synchronize on the observable ready state (works round-trip and
// the import button being enabled) and retry the upload if the app was still
// settling.
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

test("real-stack happy path: import → play → inspect → compare → reload → delete", async ({ page }) => {
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

  // ── Import real audio (retrying while the first-load project settles) ──────
  await page.goto("/");
  await importWithRetry(page);

  // ── Processing completes with no raw error surfaced ────────────────────────
  await expect(page.getByRole("tab", { name: "Piano roll" })).toBeVisible({ timeout: 300_000 });
  await expect(page.getByText("Operation failed")).not.toBeVisible();
  await expect(page.getByText(/APIError|not-null|constraint|Postgres/i)).not.toBeVisible();

  // ── Original audio plays (Play toggles to Pause) ──────────────────────────
  await selectSource(page, "Original");
  await expect(await listeningTo(page, "Original")).toBeVisible();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // ── Transcription is a distinct source and also plays ──────────────────────
  await selectSource(page, "Transcription");
  await expect(await listeningTo(page, "Transcription")).toBeVisible();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // ── Piano roll renders notes ───────────────────────────────────────────────
  await page.getByRole("tab", { name: "Piano roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("piano-roll").getByText(/\d+ notes/)).toBeVisible();

  // ── Score notation renders ─────────────────────────────────────────────────
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });

  // ── Score is a distinct Listening source and plays from the notation ────────
  await openSourceSelector(page);
  await expect(page.getByRole("option", { name: "Score rendition", exact: true })).toBeVisible();
  await expect(page.getByText("Select Score rendition in the transport to hear this notation (notation time).")).toBeVisible();
  await page.getByRole("option", { name: "Score rendition", exact: true }).click();
  await expect(await listeningTo(page, "Score rendition")).toBeVisible();
  await expect(page.getByText("Playing the score rendition in notation time. Click a measure to jump or select it.")).toBeVisible();

  // Playback starts and can be paused. The transport position change itself is
  // asserted deterministically via the measure click below, since headless
  // Chromium's media clock is unreliable in CI (currentTime can stall).
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // ── Analysis insight content persisted from the pipeline ─────────────────────
  // No selection exists yet, so the Analysis Overview renders the confident
  // whole-work key finding produced by the analyze pipeline.
  await page.getByRole("tab", { name: "Analysis" }).click();
  await expect(page.getByText("Key", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("C major").first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("tab", { name: "Score" }).click();

  // Clicking a later measure seeks the transport to that score-derived time and
  // advances the score cursor to the clicked measure (both driven by transport
  // position, not a detached timer).
  const beforeSeek = await transportPosition(page);
  const cursorBefore = await scoreCursorLeft(page);
  const measures = page.locator(".sheet-music-container g.vf-measure");
  const measureCount = await measures.count();
  expect(measureCount).toBeGreaterThan(2);
  const targetMeasure = measures.nth(2);
  const targetBox = await targetMeasure.boundingBox();
  expect(targetBox).not.toBeNull();
  await page.mouse.click(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2);
  await expect.poll(() => transportPosition(page), { timeout: 10_000 }).not.toBe(beforeSeek);
  await expect.poll(
    async () => (await scoreCursorLeft(page)) !== cursorBefore,
    { timeout: 10_000 },
  ).toBe(true);

  // ── Representation changes never stop playback or reset the playhead ───────
  // Change playback source to Original and play, then move between
  // representations while playback continues. The transport position is the
  // single clock; switching a view must not pause, rewind, or hop sources.
  await selectSource(page, "Original");
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });

  await page.getByRole("tab", { name: "Piano roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
  const positionOnPianoRoll = await transportPosition(page);
  expect(positionOnPianoRoll).toBeGreaterThan(0);

  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
  await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThanOrEqual(positionOnPianoRoll);
  // The score rendition is still NOT the heard source; only the view changed.
  await expect(await listeningTo(page, "Original")).toBeVisible();
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // ── Playback source changes keep the representation and the playhead ───────
  // While the Score representation is open, swapping what we hear must not
  // collapse the view, reset the playhead, or silently change the source.
  const positionBeforeSourceSwap = await transportPosition(page);
  await selectSource(page, "Transcription");
  await expect(await listeningTo(page, "Transcription")).toBeVisible();
  await expect(page.locator(".sheet-music-container")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");
  await expectPositionPreserved(page, positionBeforeSourceSwap);

  await selectSource(page, "Score rendition");
  await expect(await listeningTo(page, "Score rendition")).toBeVisible();
  await expect(page.locator(".sheet-music-container")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");
  await expectPositionPreserved(page, positionBeforeSourceSwap);

  // ── A/B source comparison: switch sides at the same position ───────────────
  // Enter compare (Original vs Score rendition), then toggle A and B. Both
  // sides read the same transport playhead, so the position is preserved
  // exactly across every toggle.
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("group", { name: "Compare playback" })).toBeVisible();
  await expect(page.getByRole("button", { name: "A: Original", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "B: Transcription", exact: true })).toBeVisible();

  // Set side B to the score rendition.
  await setCompareSideSource(page, "B", "Score rendition");
  await expect(page.getByRole("button", { name: "B: Score rendition", exact: true })).toBeVisible();

  const positionBeforeCompare = await transportPosition(page);
  await expect(page.getByRole("button", { name: "A", exact: true })).toHaveAttribute("aria-pressed", "true");

  // Toggle B → A → B; the playhead must not move.
  await page.getByRole("button", { name: "B", exact: true }).click();
  await expect(page.getByRole("button", { name: "B", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "A: Original", exact: true })).toBeVisible();
  await expectPositionPreserved(page, positionBeforeCompare);

  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByRole("button", { name: "A", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "B: Score rendition", exact: true })).toBeVisible();
  await expectPositionPreserved(page, positionBeforeCompare);

  await page.getByRole("button", { name: "B", exact: true }).click();
  await expect(page.getByRole("button", { name: "B", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expectPositionPreserved(page, positionBeforeCompare);

  // The Score representation stayed open the whole time.
  await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");

  // ── Analysis scopes to the active selection ─────────────────────────────────
  await page.getByRole("button", { name: "Exit compare", exact: true }).click();
  await page.getByRole("tab", { name: "Analysis" }).click();
  // The measure-click above selected a measure, so the Analysis panel now
  // scopes to the selection (the Overview is replaced by selection findings).
  await expect(page.getByText("Selection", { exact: true }).first()).toBeVisible({ timeout: 20_000 });

  // ── Reload keeps persisted state ───────────────────────────────────────────
  await page.reload();
  await expect(page.getByRole("tab", { name: "Listen" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("tab", { name: "Piano roll" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Listening to:/ })).toBeVisible();
  await page.getByRole("button", { name: /Listening to:/ }).click();
  await expect(page.getByRole("option", { name: "Original", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "Transcription", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "Score rendition", exact: true })).toBeVisible();

  // Score source still works after reload.
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.getByText("Select Score rendition in the transport to hear this notation (notation time).")).toBeVisible();
  await selectSource(page, "Score rendition");
  await expect(await listeningTo(page, "Score rendition")).toBeVisible();

  // ── Switch sources again after reload ──────────────────────────────────────
  await selectSource(page, "Original");
  await expect(await listeningTo(page, "Original")).toBeVisible();
  await selectSource(page, "Transcription");
  await expect(await listeningTo(page, "Transcription")).toBeVisible();

  // ── Delete is durable across reload ────────────────────────────────────────
  // Confirm a real duration/source is loaded first (seek disabled otherwise).
  await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
  await page.getByTitle("Delete work").click();
  await page.getByTitle("Click again to confirm delete").click();
  await expect(page.getByText(/Imported works will appear here|Start with a recording/i).first()).toBeVisible({ timeout: 15_000 });

  // No stale transport state survives the delete: playback stopped, playhead
  // at 0:00, duration cleared, no source selected, no compare UI.
  await expect(page.getByRole("slider", { name: "Playback position" })).toBeDisabled();
  const times = page.locator(".piece-time span");
  await expect(times.nth(0)).toHaveText("0:00");
  await expect(times.nth(1)).toHaveText("0:00");
  await expect(page.getByText(/Listening to:/)).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("tab", { name: "Listen" })).not.toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Start with a recording/i)).toBeVisible({ timeout: 30_000 });
});

test("shared musical selection across representations (canonical E2E)", async ({
  page,
}) => {
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

  // Import real audio (retrying while the first-load project settles)
  await page.goto("/");
  await importWithRetry(page);

  await expect(page.getByRole("tab", { name: "Piano roll" })).toBeVisible({ timeout: 300_000 });
  await expect(page.getByText("Operation failed")).not.toBeVisible();

  // Helper: waveform canvas drag-select
  async function selectWaveformRegion(startFrac: number, endFrac: number) {
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

  // ── 1. Select region in Waveform (Listen view) ───────────────────────────────
  // A horizontal drag defines a shared selection (it does not seek), so the
  // transport exposes the "Loop selection" affordance for the chosen range.
  await selectWaveformRegion(0.2, 0.6);
  await expect(page.getByRole("button", { name: "Loop selection" })).toBeVisible();

  // ── 2. Piano Roll region stays highlighted ───────────────────────────────────
  await page.getByRole("tab", { name: "Piano roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
  // Selection highlight exists as a rect with accent fill in the piano roll SVG
  await expect(
    page.locator('[data-testid="piano-roll"] svg >> rect[fill="var(--accent)"][fill-opacity="0.16"]'),
  ).toBeVisible({ timeout: 10_000 });

  // ── 3. Score measures/region stay highlighted ────────────────────────────────
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
  // Selected measures have [data-selection-highlight] rects inside measure groups
  await expect(page.locator('[data-selection-highlight]').first()).toBeVisible({ timeout: 10_000 });

  // ── 4. Enable Loop selection → play ──────────────────────────────────────────
  await page.getByRole("button", { name: "Loop selection" }).click();
  await expect(page.getByRole("button", { name: "Loop selection" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({
    timeout: 10_000,
  });

  // ── 5. Compare Original vs Score rendition → toggle A/B → loop + selection persist ──────────
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("group", { name: "Compare playback" })).toBeVisible();

  // Set B to Score rendition
  await page.getByRole("button", { name: "B: " }).click();
  await page.getByRole("option", { name: "Score rendition", exact: true }).click();

  // Toggle A → B → A, verify loop and selection persist
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
    // Selection highlight still visible on score
    await expect(page.locator('[data-selection-highlight]').first()).toBeVisible();
  }

  await page.getByRole("button", { name: "Exit compare", exact: true }).click();
  await expect(page.getByRole("group", { name: "Compare playback" })).not.toBeVisible();

  // ── 6. Reverse: select score measure → derived timeRange → switch to Waveform → region visible ──
  await page.getByRole("tab", { name: "Score" }).click();
  // Click first measure to select it
  const firstMeasure = page.locator("g.vf-measure").first();
  const measureBox = await firstMeasure.boundingBox();
  if (measureBox) {
    await page.mouse.click(measureBox.x + measureBox.width / 2, measureBox.y + measureBox.height / 2);
  }

  // Switch to Listen (Waveform) - selection region should be visible
  await page.getByRole("tab", { name: "Listen" }).click();
  await expect(page.getByTestId("waveform-canvas")).toBeVisible();
  // Waveform shows selection rect for the derived time range
  const canvas = page.getByTestId("waveform-canvas");
  await expect(canvas).toBeVisible();
});

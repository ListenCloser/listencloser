import { expect, test } from "@playwright/test";
import { readFileSync, existsSync } from "node:fs";

/**
 * Real-stack Inspector test.
 *
 * Uses pre-processed work from global setup. Exercises the contextual
 * analysis inspector against the real backend + worker + local Supabase.
 */

interface SetupResult {
  accessToken: string;
  refreshToken: string;
  user: Record<string, unknown>;
  projectId: string;
  workId: string;
  versionId: string;
  storageKey: string;
}

function loadSetup(): SetupResult | null {
  const path = "/tmp/real-stack-setup.json";
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf-8"));
}

function injectAuth(page: import("@playwright/test").Page, setup: SetupResult) {
  return page.addInitScript(
    ({ key, session }) => {
      window.localStorage.setItem(
        key,
        JSON.stringify({
          access_token: session.accessToken,
          token_type: "bearer",
          expires_in: 3600,
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          refresh_token: session.refreshToken,
          user: session.user,
        }),
      );
    },
    { key: setup.storageKey, session: setup },
  );
}

async function transportPosition(page: import("@playwright/test").Page): Promise<number> {
  return Number(await page.getByRole("slider", { name: "Playback position" }).inputValue());
}

async function selectSource(page: import("@playwright/test").Page, label: string) {
  await page.getByRole("button", { name: /Listening to:/ }).click();
  await page.getByRole("option", { name: label, exact: true }).click();
}

const SHOTS = "docs/pr/224";

test("inspect the real workspace: play → whole-piece → selection → score → collapse → drawer", async ({ page }) => {
  const setup = loadSetup();
  test.skip(!setup, "global setup did not produce /tmp/real-stack-setup.json");

  await page.setViewportSize({ width: 1440, height: 900 });
  await injectAuth(page, setup!);
  await page.goto("/");

  // Wait for pre-processed work to load
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 60_000 });
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

  // ── Seek to a real insight ──────────────────────────────────────────────
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

  // ── Sparse selection state ──────────────────────────────────────────────
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

  // ── Collapse the inspector ──────────────────────────────────────────────
  await page.getByRole("button", { name: "Hide analysis" }).click();
  await expect(page.locator(".inspector")).toHaveCount(0);
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/06-inspector-collapsed.png` });
  await page.getByRole("button", { name: "Show analysis" }).click();
  await expect(page.locator(".inspector")).toBeVisible();

  // ── Mid width (1024px) ──────────────────────────────────────────────────
  await page.setViewportSize({ width: 1024, height: 900 });
  await expect(page.locator(".inspector")).toBeVisible();
  await expect(page.locator(".studio-inspector-backdrop")).not.toBeVisible();

  // ── Narrow width: drawer ────────────────────────────────────────────────
  await page.setViewportSize({ width: 768, height: 900 });
  await expect(page.locator(".studio-inspector-backdrop")).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: `${SHOTS}/07-narrow-width-drawer.png` });
  await page.locator(".studio-inspector-backdrop").click({ position: { x: 10, y: 450 } });
  await expect(page.locator(".inspector")).toHaveCount(0);
  await page.getByRole("button", { name: "Show analysis" }).click();
  await expect(page.locator(".inspector")).toBeVisible();
});

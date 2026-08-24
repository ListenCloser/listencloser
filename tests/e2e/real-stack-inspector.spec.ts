import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { injectAuth } from "./real-stack-auth";

const REAL_AUDIO = process.env.REAL_AUDIO_FILE;
const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

const SHOTS = "docs/pr/224";

async function transportPosition(page: import("@playwright/test").Page): Promise<number> {
  return Number(await page.getByRole("slider", { name: "Playback position" }).inputValue());
}

async function selectSource(page: import("@playwright/test").Page, label: string) {
  await page.getByRole("button", { name: /Listening to:/ }).click();
  await page.getByRole("option", { name: label, exact: true }).click();
}

test("inspect the real workspace: play → whole-piece → selection → score → collapse → drawer", async ({ page }) => {
  test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required (no fallback fixture)");
  test.skip(!existsSync(REAL_AUDIO!), `REAL_AUDIO_FILE does not exist: ${REAL_AUDIO}`);
  test.skip(!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY, "local Supabase env not configured");

  await page.setViewportSize({ width: 1440, height: 900 });
  await injectAuth(page);
  await page.goto("/");
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 300_000 });
  await expect(page.getByText("Operation failed")).not.toBeVisible();

  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.locator(".inspector")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/01-listen-whole-piece-inspector.png` });

  await selectSource(page, "Original");
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(".inspector")).toBeVisible();
  const posPlaying = await transportPosition(page);
  await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThanOrEqual(posPlaying);
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  const seekable = page.locator(".inspector .inspector-observation, .inspector .rn-chip").first();
  if (await seekable.count().catch(() => 0)) {
    const beforeSeek = await transportPosition(page);
    await seekable.click();
    await expect.poll(() => transportPosition(page), { timeout: 10_000 }).not.toBe(beforeSeek);
    await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThan(0);
  }

  const canvas = page.getByTestId("waveform-canvas");
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  if (!box) throw new Error("waveform canvas not found");
  await page.mouse.move(box.x + box.width * 0.2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2, { steps: 6 });
  await page.mouse.up();
  await expect(page.locator(".inspector-scope-label", { hasText: "Selection" })).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: `${SHOTS}/02-listen-selection-inspector.png` });

  await page.getByRole("tab", { name: "Piano Roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".inspector")).toBeVisible();
  await expect(page.locator(".inspector-scope-label", { hasText: "Selection" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/03-piano-roll-selected-region-inspector.png` });

  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".inspector")).toBeVisible();
  await expect(page.locator(".inspector-scope-label", { hasText: "Selection" })).toBeVisible();

  const measures = page.locator(".sheet-music-container g.vf-measure");
  await expect.poll(async () => measures.count(), { timeout: 30_000 }).toBeGreaterThan(1);
  const targetMeasure = measures.nth(1);
  const targetBox = await targetMeasure.boundingBox();
  expect(targetBox).not.toBeNull();
  await page.mouse.click(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2);
  await expect(page.getByText(/Measures \d+–\d+/)).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: `${SHOTS}/04-score-selected-measures-inspector.png` });

  await page.getByRole("tab", { name: "Waveform" }).click();
  await expect(canvas).toBeVisible();
  const box2 = await canvas.boundingBox();
  if (box2) {
    await page.mouse.move(box2.x + box2.width * 0.92, box2.y + box2.height / 2);
    await page.mouse.down();
    await page.mouse.move(box2.x + box2.width * 0.97, box2.y + box2.height / 2, { steps: 3 });
    await page.mouse.up();
  }
  await page.screenshot({ path: `${SHOTS}/05-sparse-analysis.png` });

  await page.getByRole("button", { name: "Hide analysis" }).click();
  await expect(page.locator(".inspector")).toHaveCount(0);
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/06-inspector-collapsed.png` });
  await page.getByRole("button", { name: "Show analysis" }).click();
  await expect(page.locator(".inspector")).toBeVisible();

  await page.setViewportSize({ width: 1024, height: 900 });
  await expect(page.locator(".inspector")).toBeVisible();
  await expect(page.locator(".studio-inspector-backdrop")).not.toBeVisible();

  await page.setViewportSize({ width: 768, height: 900 });
  await expect(page.locator(".studio-inspector-backdrop")).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: `${SHOTS}/07-narrow-width-drawer.png` });
  await page.locator(".studio-inspector-backdrop").click({ position: { x: 10, y: 450 } });
  await expect(page.locator(".inspector")).toHaveCount(0);
  await page.getByRole("button", { name: "Show analysis" }).click();
  await expect(page.locator(".inspector")).toBeVisible();
});

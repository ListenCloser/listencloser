import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { injectAuth, dismissWorkspaceNotice } from "./real-stack-auth";

/**
 * Real-stack golden-path test.
 *
 * Answers one question: "Can a real user successfully complete our critical
 * end-to-end product workflow against the actual stack?"
 *
 * Imports real-piano.m4a exactly ONCE, then exercises transcription,
 * analysis, persistence, and deletion in a single sequential journey.
 */

const REAL_AUDIO = process.env.REAL_AUDIO_FILE;
const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

async function transportPosition(page: import("@playwright/test").Page): Promise<number> {
  return Number(await page.getByRole("slider", { name: "Playback position" }).inputValue());
}

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

async function openSourceSelector(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: /Playback source:/ }).click();
}

async function selectSource(page: import("@playwright/test").Page, label: string) {
  const selected = page.getByRole("button", { name: `Playback source: ${label}`, exact: true });
  if (await selected.isVisible().catch(() => false)) return;
  await openSourceSelector(page);
  await page.getByRole("option", { name: label, exact: true }).click();
}

async function listeningTo(page: import("@playwright/test").Page, label: string) {
  return page.getByRole("button", { name: `Playback source: ${label}`, exact: true });
}

async function setCompareSideSource(page: import("@playwright/test").Page, side: "A" | "B", label: string) {
  const trigger = page.getByRole("button", { name: `${side} compare source`, exact: true });
  if ((await trigger.textContent())?.trim() === label) return;
  await trigger.click();
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
    await page.getByRole("menuitem", { name: /Upload recording/ }).click();
    await page.locator('input[type="file"]').setInputFiles(REAL_AUDIO!);

    const processing = page.getByRole("progressbar");
    const failed = page.getByRole("alert").filter({ hasText: "Your project is still loading" });
    const outcome = await Promise.race([
      processing.waitFor({ state: "visible", timeout: 15_000 }).then(() => "started"),
      failed.waitFor({ state: "visible", timeout: 15_000 }).then(() => "failed"),
    ]);
    if (outcome === "started") return;
    await failed.getByRole("button", { name: "Try another file" }).click();
    await expect(failed).toBeHidden({ timeout: 10_000 });
  }
  throw new Error("import did not start after retries");
}

async function selectWaveformRegion(page: import("@playwright/test").Page, startFrac: number, endFrac: number) {
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

test("real audio golden path", async ({ page }) => {
  test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required");
  test.skip(!existsSync(REAL_AUDIO!), `REAL_AUDIO_FILE does not exist: ${REAL_AUDIO}`);
  test.skip(!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY, "local Supabase env not configured");

  await injectAuth(page);
  await page.goto("/");

  // ── Import and processing ────────────────────────────────────────────
  await test.step("import and processing", async () => {
    await importWithRetry(page);
    await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 300_000 });
    await expect(page.getByText("Operation failed")).not.toBeVisible();
    await dismissWorkspaceNotice(page);
  });

  // ── Transcription representations ────────────────────────────────────
  await test.step("transcription representations", async () => {
    // Original audio plays
    await selectSource(page, "Original");
    await expect(await listeningTo(page, "Original")).toBeVisible();
    await page.getByRole("button", { name: "Play Original", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause Original", exact: true })).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Pause Original", exact: true }).click();

    // Transcription plays
    await selectSource(page, "Transcription");
    await expect(await listeningTo(page, "Transcription")).toBeVisible();
    await page.getByRole("button", { name: "Play Transcription", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause Transcription", exact: true })).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Pause Transcription", exact: true }).click();

    // Piano roll renders notes
    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("piano-roll").getByText(/\d+ notes/)).toBeVisible();

    // Score renders
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });

    // A rendered Score must also have its distinct notation-derived playback source.
    await openSourceSelector(page);
    const scoreRendition = page.getByRole("option", { name: "Score", exact: true });
    await expect(scoreRendition).toBeVisible({ timeout: 10_000 });
    await scoreRendition.click();
    await expect(await listeningTo(page, "Score")).toBeVisible();
    await page.getByRole("button", { name: "Play Score", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause Score", exact: true })).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Pause Score", exact: true }).click();
  });

  // ── Breakdown ────────────────────────────────────────────────────────
  await test.step("breakdown", async () => {
    await page.getByRole("tab", { name: "Breakdown" }).click();
    // Verify supported analysis reached Breakdown without requiring any one
    // optional context detector (such as key) to produce a confident result.
    await expect(page.getByRole("heading", { name: "What stands out" })).toBeVisible({ timeout: 30_000 });
  });

  // ── Annotations and Inspector ────────────────────────────────────────
  await test.step("annotations and inspector", async () => {
    // Score measure click owns two contracts: it seeks the active score
    // timeline and creates the shared measure selection. The visible playback
    // cursor is driven by playback-follow state, so selection should not be
    // coupled to OSMD's legacy hidden cursor element.
    await page.getByRole("tab", { name: "Score" }).click();
    const measures = page.locator(".sheet-music-container g.vf-measure");
    const measureCount = await measures.count();
    expect(measureCount).toBeGreaterThan(2);
    const logicalThirdMeasure = page.locator('.sheet-music-container g.vf-measure[id="3"]').first();
    await expect(logicalThirdMeasure).toBeAttached();
    const targetBox = await logicalThirdMeasure.boundingBox();
    expect(targetBox).not.toBeNull();
    const beforeSeek = await transportPosition(page);
    await page.mouse.click(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2);
    await expect
      .poll(
        async () => Math.abs((await transportPosition(page)) - beforeSeek) > 0.1,
        { timeout: 10_000, message: "score measure click should seek the active score timeline" },
      )
      .toBe(true);
    await expect(page.locator("[data-selection-highlight]").first()).toBeVisible({ timeout: 10_000 });

    // Representation changes preserve playback
    await selectSource(page, "Original");
    await page.getByRole("button", { name: "Play Original", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause Original", exact: true })).toBeVisible({ timeout: 10_000 });

    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible();
    await expect(page.getByRole("button", { name: "Pause Original", exact: true })).toBeVisible();
    const positionOnPianoRoll = await transportPosition(page);
    expect(positionOnPianoRoll).toBeGreaterThan(0);

    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible();
    await expect(page.getByRole("button", { name: "Pause Original", exact: true })).toBeVisible();
    await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThanOrEqual(positionOnPianoRoll);
    await expect(await listeningTo(page, "Original")).toBeVisible();
    await page.getByRole("button", { name: "Pause Original", exact: true }).click();

    // Source swap preserves playhead
    const positionBeforeSourceSwap = await transportPosition(page);
    await selectSource(page, "Transcription");
    await expect(await listeningTo(page, "Transcription")).toBeVisible();
    await expectPositionPreserved(page, positionBeforeSourceSwap);

    // Score source swap is part of the production Score contract, not optional.
    await openSourceSelector(page);
    const scoreRenditionOption = page.getByRole("option", { name: "Score", exact: true });
    await expect(scoreRenditionOption).toBeVisible({ timeout: 10_000 });
    await scoreRenditionOption.click();
    await expect(await listeningTo(page, "Score")).toBeVisible();
    await expectPositionPreserved(page, positionBeforeSourceSwap);

    // A/B comparison
    await page.getByRole("button", { name: "Compare", exact: true }).click();
    await expect(page.getByRole("group", { name: "Compare playback sources" })).toBeVisible();

    // Use Transcription for B side; the helper is idempotent because compare already defaults B to it.
    await setCompareSideSource(page, "B", "Transcription");
    await expect(page.getByRole("button", { name: "B compare source", exact: true })).toContainText("Transcription");

    const positionBeforeCompare = await transportPosition(page);
    await page.getByRole("button", { name: "B", exact: true }).click();
    await expectPositionPreserved(page, positionBeforeCompare);
    await page.getByRole("button", { name: "A", exact: true }).click();
    await expectPositionPreserved(page, positionBeforeCompare);
    await page.getByRole("button", { name: "B", exact: true }).click();
    await expectPositionPreserved(page, positionBeforeCompare);
    await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");

    // Breakdown scopes to selection
    await page.getByRole("button", { name: "Exit compare", exact: true }).click();
    await page.getByRole("tab", { name: "Breakdown" }).click();
    const inspectorScope = page.locator("aside.inspector");
    await expect(inspectorScope.getByRole("button", { name: "Clear selection" })).toBeVisible({ timeout: 20_000 });
    await expect(inspectorScope.locator(".inspector-scope-value")).toHaveText(/\d+:\d{2}–\d+:\d{2}/);

    // Shared selection across representations
    await page.getByRole("tab", { name: "Waveform" }).click();
    await selectWaveformRegion(page, 0.2, 0.6);
    const loop = page.getByRole("button", { name: "Toggle selected passage loop" });
    await expect(loop).toBeVisible();
    await expect(loop).toBeEnabled();
    await expect(page.getByRole("button", { name: "Loop selection" })).toHaveCount(0);

    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
    await expect(
      page.locator('[data-testid="piano-roll"] [data-selection-range]'),
    ).toBeVisible({ timeout: 10_000 });

    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-selection-highlight]').first()).toBeVisible({ timeout: 10_000 });

    // Desktop Inspector is a persistent dock. Verify its selected Breakdown
    // mode instead of stale show/hide controls that intentionally no longer exist.
    const inspector = page.locator("aside.inspector");
    await expect(inspector).toBeVisible();
    await expect(inspector.getByRole("tab", { name: "Breakdown", selected: true })).toBeVisible();
  });

  // ── Persistence ──────────────────────────────────────────────────────
  await test.step("persistence", async () => {
    await page.reload();
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible({ timeout: 30_000 });
    await dismissWorkspaceNotice(page);
    await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Breakdown" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Playback source:/ })).toBeVisible();
    await page.getByRole("button", { name: /Playback source:/ }).click();
    await expect(page.getByRole("option", { name: "Original", exact: true })).toBeVisible();
    await expect(page.getByRole("option", { name: "Transcription", exact: true })).toBeVisible();
    await expect(page.getByRole("option", { name: "Score", exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
  });

  // ── Deletion ─────────────────────────────────────────────────────────
  await test.step("deletion", async () => {
    await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
    const deleteRecording = page.getByRole("button", { name: /^Delete / }).first();
    await expect(deleteRecording).toBeVisible();
    await deleteRecording.click();
    await expect(page.getByRole("heading", { name: "Import a recording" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("slider", { name: "Playback position" })).toHaveCount(0);
    await expect(page.locator(".transport-time")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Playback source:/ })).toHaveCount(0);

    await page.reload();
    await expect(page.getByRole("tab", { name: "Waveform" })).not.toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: "Import a recording" })).toBeVisible({ timeout: 30_000 });
  });
});
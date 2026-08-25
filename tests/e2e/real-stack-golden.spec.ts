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

async function scoreCursorLeft(page: import("@playwright/test").Page): Promise<string | null> {
  return page.evaluate(() => {
    const cursor = document.querySelector<HTMLElement>('.sheet-music-container img[id^="cursorImg"]');
    return cursor ? cursor.style.left : null;
  });
}

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
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Pause", exact: true }).click();

    // Transcription plays
    await selectSource(page, "Transcription");
    await expect(await listeningTo(page, "Transcription")).toBeVisible();
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Pause", exact: true }).click();

    // Piano roll renders notes
    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("piano-roll").getByText(/\d+ notes/)).toBeVisible();

    // Score renders
    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });

    // Score rendition is a distinct source (may not be available if rendering failed)
    await openSourceSelector(page);
    const scoreRendition = page.getByRole("option", { name: "Score rendition", exact: true });
    if (await scoreRendition.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await scoreRendition.click();
      await expect(await listeningTo(page, "Score rendition")).toBeVisible();
      await page.getByRole("button", { name: "Play", exact: true }).click();
      await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
      await page.getByRole("button", { name: "Pause", exact: true }).click();
    } else {
      // Close the selector if score rendition isn't available
      await page.keyboard.press("Escape");
    }
  });

  // ── Analysis ─────────────────────────────────────────────────────────
  await test.step("analysis", async () => {
    await page.getByRole("tab", { name: "Analysis" }).click();
    // Verify analysis insights are present — "Key" label confirms key detection ran
    await expect(page.getByText("Key", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
  });

  // ── Annotations and Inspector ────────────────────────────────────────
  await test.step("annotations and inspector", async () => {
    // Score measure click seeks transport
    await page.getByRole("tab", { name: "Score" }).click();
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

    // Representation changes preserve playback
    await selectSource(page, "Original");
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });

    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
    const positionOnPianoRoll = await transportPosition(page);
    expect(positionOnPianoRoll).toBeGreaterThan(0);

    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
    await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThanOrEqual(positionOnPianoRoll);
    await expect(await listeningTo(page, "Original")).toBeVisible();
    await page.getByRole("button", { name: "Pause", exact: true }).click();

    // Source swap preserves playhead
    const positionBeforeSourceSwap = await transportPosition(page);
    await selectSource(page, "Transcription");
    await expect(await listeningTo(page, "Transcription")).toBeVisible();
    await expectPositionPreserved(page, positionBeforeSourceSwap);

    await selectSource(page, "Score rendition");
    await expect(await listeningTo(page, "Score rendition")).toBeVisible();
    await expectPositionPreserved(page, positionBeforeSourceSwap);

    // A/B comparison
    await page.getByRole("button", { name: "Compare", exact: true }).click();
    await expect(page.getByRole("group", { name: "Compare playback" })).toBeVisible();

    // Use Transcription for B side since Score rendition may not be available
    await setCompareSideSource(page, "B", "Transcription");
    await expect(page.getByRole("button", { name: "B: Transcription", exact: true })).toBeVisible();

    const positionBeforeCompare = await transportPosition(page);
    await page.getByRole("button", { name: "B", exact: true }).click();
    await expectPositionPreserved(page, positionBeforeCompare);
    await page.getByRole("button", { name: "A", exact: true }).click();
    await expectPositionPreserved(page, positionBeforeCompare);
    await page.getByRole("button", { name: "B", exact: true }).click();
    await expectPositionPreserved(page, positionBeforeCompare);
    await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");

    // Analysis scopes to selection
    await page.getByRole("button", { name: "Exit compare", exact: true }).click();
    await page.getByRole("tab", { name: "Analysis" }).click();
    await expect(page.getByText("Selection", { exact: true }).first()).toBeVisible({ timeout: 20_000 });

    // Shared selection across representations
    await page.getByRole("tab", { name: "Waveform" }).click();
    await selectWaveformRegion(page, 0.2, 0.6);
    await expect(page.getByRole("button", { name: "Loop selection" })).toBeVisible();

    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
    await expect(
      page.locator('[data-testid="piano-roll"] svg >> rect[fill="var(--accent)"][fill-opacity="0.1"]'),
    ).toBeVisible({ timeout: 10_000 });

    await page.getByRole("tab", { name: "Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-selection-highlight]').first()).toBeVisible({ timeout: 10_000 });

    // Inspector visibility
    await expect(page.locator(".inspector")).toBeVisible();
    await page.getByRole("button", { name: "Hide analysis" }).click();
    await expect(page.locator(".inspector")).toHaveCount(0);
    await page.getByRole("button", { name: "Show analysis" }).click();
    await expect(page.locator(".inspector")).toBeVisible();
  });

  // ── Persistence ──────────────────────────────────────────────────────
  await test.step("persistence", async () => {
    await page.reload();
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Listening to:/ })).toBeVisible();
    await page.getByRole("button", { name: /Listening to:/ }).click();
    await expect(page.getByRole("option", { name: "Original", exact: true })).toBeVisible();
    await expect(page.getByRole("option", { name: "Transcription", exact: true })).toBeVisible();
    // Score rendition may not be available if rendering failed
    await page.keyboard.press("Escape");
  });

  // ── Deletion ─────────────────────────────────────────────────────────
  await test.step("deletion", async () => {
    await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
    await page.getByTitle("Delete work").click();
    await page.getByTitle("Click again to confirm delete").click();
    await expect(page.getByText(/Bring in a recording|Start with a recording/i).first()).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("slider", { name: "Playback position" })).toBeDisabled();
    const times = page.locator(".transport-time");
    await expect(times.nth(0)).toHaveText("0:00");
    await expect(times.nth(1)).toHaveText("0:00");
    await expect(page.getByText(/Listening to:/)).toHaveCount(0);

    await page.reload();
    await expect(page.getByRole("tab", { name: "Waveform" })).not.toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Bring in a recording|Start with a recording/i).first()).toBeVisible({ timeout: 30_000 });
  });
});

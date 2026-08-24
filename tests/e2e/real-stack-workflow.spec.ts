import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";

/**
 * Real-stack workflow tests.
 *
 * These tests run AFTER the setup project has:
 *   1. Created a Supabase test user
 *   2. Imported real-piano.m4a
 *   3. Waited for the full pipeline to complete
 *   4. Saved browser storageState with the authenticated session
 *
 * Each test gets an isolated browser context with the storageState loaded,
 * so the Supabase client finds the session in localStorage and the app
 * auto-loads the existing work.
 */

const REAL_AUDIO = process.env.REAL_AUDIO_FILE;

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

test("play → inspect → compare → reload", async ({ page }) => {
  test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required");

  // Navigate — app should auto-load the existing work from storageState
  await page.goto("/");
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Operation failed")).not.toBeVisible();

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

  // Score notation renders
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });

  // Score is a distinct Listening source
  await openSourceSelector(page);
  await expect(page.getByRole("option", { name: "Score rendition", exact: true })).toBeVisible();
  await page.getByRole("option", { name: "Score rendition", exact: true }).click();
  await expect(await listeningTo(page, "Score rendition")).toBeVisible();

  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // Analysis insight content
  await page.getByRole("tab", { name: "Analysis" }).click();
  await expect(page.getByText("Key", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("C major").first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("tab", { name: "Score" }).click();

  // Measure click seeks transport
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

  await setCompareSideSource(page, "B", "Score rendition");
  await expect(page.getByRole("button", { name: "B: Score rendition", exact: true })).toBeVisible();

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

  // Reload keeps persisted state
  await page.reload();
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Listening to:/ })).toBeVisible();
  await page.getByRole("button", { name: /Listening to:/ }).click();
  await expect(page.getByRole("option", { name: "Original", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "Transcription", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "Score rendition", exact: true })).toBeVisible();
});

test("shared musical selection across representations", async ({ page }) => {
  test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required");

  await page.goto("/");
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Operation failed")).not.toBeVisible();

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

  await selectWaveformRegion(0.2, 0.6);
  await expect(page.getByRole("button", { name: "Loop selection" })).toBeVisible();

  await page.getByRole("tab", { name: "Piano Roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
  await expect(
    page.locator('[data-testid="piano-roll"] svg >> rect[fill="var(--accent)"][fill-opacity="0.1"]'),
  ).toBeVisible({ timeout: 10_000 });

  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('[data-selection-highlight]').first()).toBeVisible({ timeout: 10_000 });

  await page.getByRole("button", { name: "Loop selection" }).click();
  await expect(page.getByRole("button", { name: "Loop selection" })).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });

  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("group", { name: "Compare playback" })).toBeVisible();

  await page.getByRole("button", { name: "B: " }).click();
  await page.getByRole("option", { name: "Score rendition", exact: true }).click();

  for (const side of ["B", "A", "B"] as const) {
    await page.getByRole("button", { name: side, exact: true }).click();
    await expect(page.getByRole("button", { name: side, exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("button", { name: "Loop selection" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('[data-selection-highlight]').first()).toBeVisible();
  }

  await page.getByRole("button", { name: "Exit compare", exact: true }).click();
  await expect(page.getByRole("group", { name: "Compare playback" })).not.toBeVisible();

  await page.getByRole("tab", { name: "Score" }).click();
  const firstMeasure = page.locator("g.vf-measure").first();
  const measureBox = await firstMeasure.boundingBox();
  if (measureBox) {
    await page.mouse.click(measureBox.x + measureBox.width / 2, measureBox.y + measureBox.height / 2);
  }

  await page.getByRole("tab", { name: "Waveform" }).click();
  await expect(page.getByTestId("waveform-canvas")).toBeVisible();
});

test("delete work and verify clean state", async ({ page }) => {
  test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required");

  await page.goto("/");
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 60_000 });

  await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
  await page.getByTitle("Delete work").click();
  await page.getByTitle("Click again to confirm delete").click();
  await expect(page.getByText(/Imported works will appear here|Start with a recording/i).first()).toBeVisible({ timeout: 15_000 });

  await expect(page.getByRole("slider", { name: "Playback position" })).toBeDisabled();
  const times = page.locator(".transport-time");
  await expect(times.nth(0)).toHaveText("0:00");
  await expect(times.nth(1)).toHaveText("0:00");
  await expect(page.getByText(/Listening to:/)).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("tab", { name: "Waveform" })).not.toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Start with a recording/i)).toBeVisible({ timeout: 30_000 });
});

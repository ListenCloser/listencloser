import { expect, test } from "@playwright/test";
import { readFileSync, existsSync } from "node:fs";

/**
 * Real-stack browser workflow test.
 *
 * Uses pre-processed work from global setup (audio imported once via API).
 * Tests the full happy path: play → inspect → compare → reload → delete.
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

test("real-stack happy path: play → inspect → compare → reload → delete", async ({ page }) => {
  const setup = loadSetup();
  test.skip(!setup, "global setup did not produce /tmp/real-stack-setup.json");

  await injectAuth(page, setup!);
  await page.goto("/");

  // The app should load the pre-processed work automatically
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 60_000 });
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
  await page.getByRole("tab", { name: "Piano Roll" }).click();
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

  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // ── Analysis insight content persisted from the pipeline ─────────────────────
  await page.getByRole("tab", { name: "Analysis" }).click();
  await expect(page.getByText("Key", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("C major").first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("tab", { name: "Score" }).click();

  // ── Measure click seeks transport ──────────────────────────────────────────
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

  // ── Playback source changes keep the representation and the playhead ───────
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

  // ── A/B source comparison ──────────────────────────────────────────────────
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("group", { name: "Compare playback" })).toBeVisible();
  await expect(page.getByRole("button", { name: "A: Original", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "B: Transcription", exact: true })).toBeVisible();

  await setCompareSideSource(page, "B", "Score rendition");
  await expect(page.getByRole("button", { name: "B: Score rendition", exact: true })).toBeVisible();

  const positionBeforeCompare = await transportPosition(page);
  await expect(page.getByRole("button", { name: "A", exact: true })).toHaveAttribute("aria-pressed", "true");

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

  await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");

  // ── Analysis scopes to the active selection ─────────────────────────────────
  await page.getByRole("button", { name: "Exit compare", exact: true }).click();
  await page.getByRole("tab", { name: "Analysis" }).click();
  await expect(page.getByText("Selection", { exact: true }).first()).toBeVisible({ timeout: 20_000 });

  // ── Reload keeps persisted state ───────────────────────────────────────────
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

  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.getByText("Select Score rendition in the transport to hear this notation (notation time).")).toBeVisible();
  await selectSource(page, "Score rendition");
  await expect(await listeningTo(page, "Score rendition")).toBeVisible();

  await selectSource(page, "Original");
  await expect(await listeningTo(page, "Original")).toBeVisible();
  await selectSource(page, "Transcription");
  await expect(await listeningTo(page, "Transcription")).toBeVisible();

  // ── Delete is durable across reload ────────────────────────────────────────
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

test("shared musical selection across representations", async ({ page }) => {
  const setup = loadSetup();
  test.skip(!setup, "global setup did not produce /tmp/real-stack-setup.json");

  await injectAuth(page, setup!);
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

  // ── 1. Select region in Waveform ───────────────────────────────────────────
  await selectWaveformRegion(0.2, 0.6);
  await expect(page.getByRole("button", { name: "Loop selection" })).toBeVisible();

  // ── 2. Piano Roll region stays highlighted ─────────────────────────────────
  await page.getByRole("tab", { name: "Piano Roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
  await expect(
    page.locator('[data-testid="piano-roll"] svg >> rect[fill="var(--accent)"][fill-opacity="0.1"]'),
  ).toBeVisible({ timeout: 10_000 });

  // ── 3. Score measures stay highlighted ─────────────────────────────────────
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('[data-selection-highlight]').first()).toBeVisible({ timeout: 10_000 });

  // ── 4. Enable Loop selection → play ────────────────────────────────────────
  await page.getByRole("button", { name: "Loop selection" }).click();
  await expect(page.getByRole("button", { name: "Loop selection" })).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });

  // ── 5. Compare with selection persisting ───────────────────────────────────
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

  // ── 6. Score measure → timeRange → Waveform ───────────────────────────────
  await page.getByRole("tab", { name: "Score" }).click();
  const firstMeasure = page.locator("g.vf-measure").first();
  const measureBox = await firstMeasure.boundingBox();
  if (measureBox) {
    await page.mouse.click(measureBox.x + measureBox.width / 2, measureBox.y + measureBox.height / 2);
  }

  await page.getByRole("tab", { name: "Waveform" }).click();
  await expect(page.getByTestId("waveform-canvas")).toBeVisible();
});

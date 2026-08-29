import { expect, test } from "@playwright/test";
import { existsSync, writeFileSync } from "node:fs";
import { injectAuth, dismissWorkspaceNotice } from "./real-stack-auth";
import {
  beginImportPerformanceAttempt,
  type ImportPerformanceTracker,
} from "./import-performance";

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

type ImportUiMilestones = {
  durable_work_visible_ms: number;
  original_source_ready_ms: number;
  waveform_ready_ms: number;
  transcription_playback_ready_ms: number;
  piano_roll_ready_ms: number;
  first_evidence_ready_ms: number;
  score_xml_ready_ms: number;
  score_render_ready_ms: number;
  workflow_terminal_ms: number;
};

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

async function importWithRetry(page: import("@playwright/test").Page): Promise<ImportPerformanceTracker> {
  await waitForProjectReady(page);
  for (let attempt = 0; attempt < 5; attempt++) {
    const importButton = page
      .getByRole("complementary")
      .getByRole("button", { name: "Import audio" });
    await expect(importButton).toBeEnabled({ timeout: 30_000 });
    await importButton.click();

    // The product-level clock starts at the user's file selection, not at the
    // first backend request. Keep this observer alive through enrichment so it
    // also captures upload/finalize/workflow responses and Work polling.
    const tracker = beginImportPerformanceAttempt(page);
    await page.locator('input[type="file"]').setInputFiles(REAL_AUDIO!);

    const processing = page.getByRole("progressbar");
    const failed = page.getByRole("alert").filter({ hasText: "Your project is still loading" });
    const outcome = await Promise.race([
      processing.waitFor({ state: "visible", timeout: 15_000 }).then(() => "started"),
      failed.waitFor({ state: "visible", timeout: 15_000 }).then(() => "failed"),
    ]);
    if (outcome === "started") return tracker;
    tracker.stop();
    await failed.getByRole("button", { name: "Try another file" }).click();
    await expect(failed).toBeHidden({ timeout: 10_000 });
  }
  throw new Error("import did not start after retries");
}

async function measureImportToUsable(
  page: import("@playwright/test").Page,
  tracker: ImportPerformanceTracker,
): Promise<ImportUiMilestones> {
  const elapsed = () => tracker.elapsedMs();

  // Durability comes first: the Library row can exist before any derived
  // representation. This separates upload/finalize cost from processing cost.
  const selectedWork = page.locator(".library-work-btn[aria-current='true']").first();
  await expect(selectedWork).toBeVisible({ timeout: 30_000 });
  const durableWorkVisible = elapsed();

  // The original recording should become usable independently of enrichment.
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible({ timeout: 30_000 });
  const originalSourceReady = elapsed();
  const waveform = page.getByTestId("waveform-canvas");
  await expect(waveform).toHaveAttribute("data-waveform-state", "ready", { timeout: 30_000 });
  const waveformReady = elapsed();

  // Transcription playback and note UI are both persisted by handle_transcribe.
  await openSourceSelector(page);
  await expect(page.getByRole("option", { name: "Transcription", exact: true })).toBeVisible({ timeout: 300_000 });
  const transcriptionPlaybackReady = elapsed();
  await page.keyboard.press("Escape");

  const pianoRollTab = page.getByRole("tab", { name: "Piano Roll" });
  await expect(pianoRollTab).toBeVisible({ timeout: 300_000 });
  await pianoRollTab.click();
  await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("piano-roll").getByText(/\d+ notes/)).toBeVisible();
  const pianoRollReady = elapsed();

  // Analysis is downstream of transcription but upstream of score in the
  // current composite understand job. Existing golden-path behavior already
  // requires Key evidence, so use that stable user-visible boundary.
  await expect(page.getByText("Key", { exact: true }).first()).toBeVisible({ timeout: 300_000 });
  const firstEvidenceReady = elapsed();

  // A Score tab is only published after MusicXML text has been fetched into the
  // workspace representation. Measure OSMD/VexFlow render separately.
  const scoreTab = page.getByRole("tab", { name: "Score" });
  await expect(scoreTab).toBeVisible({ timeout: 300_000 });
  const scoreXmlReady = elapsed();
  await scoreTab.click();
  await expect(page.locator(".sheet-music-container g.vf-measure").first()).toBeVisible({ timeout: 30_000 });
  const scoreRenderReady = elapsed();

  // The processing notice is tied to the durable job state. By the time Score
  // is ready it may already be hidden; in that case this is a conservative
  // upper-bound sample taken at observation time rather than a fabricated
  // earlier completion timestamp.
  await expect(page.locator(".workspace-processing-notice")).toBeHidden({ timeout: 300_000 });
  const workflowTerminal = elapsed();

  return {
    durable_work_visible_ms: durableWorkVisible,
    original_source_ready_ms: originalSourceReady,
    waveform_ready_ms: waveformReady,
    transcription_playback_ready_ms: transcriptionPlaybackReady,
    piano_roll_ready_ms: pianoRollReady,
    first_evidence_ready_ms: firstEvidenceReady,
    score_xml_ready_ms: scoreXmlReady,
    score_render_ready_ms: scoreRenderReady,
    workflow_terminal_ms: workflowTerminal,
  };
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

test("real audio golden path", async ({ page }, testInfo) => {
  test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required");
  test.skip(!existsSync(REAL_AUDIO!), `REAL_AUDIO_FILE does not exist: ${REAL_AUDIO}`);
  test.skip(!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY, "local Supabase env not configured");

  await injectAuth(page);
  await page.goto("/");

  // ── Import and processing ────────────────────────────────────────────
  await test.step("import and processing", async () => {
    const tracker = await importWithRetry(page);
    try {
      const uiMilestones = await measureImportToUsable(page, tracker);
      await expect(page.getByText("Operation failed")).not.toBeVisible();

      const report = {
        schema_version: 1,
        scenario: "real_import_to_usable",
        fixture: "real-piano.m4a",
        release_sha: process.env.GITHUB_SHA ?? null,
        thresholds_enforced: false,
        clock: "node_performance_now",
        network_milestones: tracker.networkMilestones,
        ui_milestones: uiMilestones,
        work_bundle_response_count: tracker.workBundleResponses.length,
        work_bundle_response_ms: tracker.workBundleResponses,
      };
      const reportPath = testInfo.outputPath("import-performance.json");
      writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
      await testInfo.attach("import-performance.json", {
        path: reportPath,
        contentType: "application/json",
      });
    } finally {
      tracker.stop();
    }
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

    // Score is a distinct source (may not be available if rendering failed)
    await openSourceSelector(page);
    const scoreRendition = page.getByRole("option", { name: "Score", exact: true });
    if (await scoreRendition.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await scoreRendition.click();
      await expect(await listeningTo(page, "Score")).toBeVisible();
      await page.getByRole("button", { name: "Play", exact: true }).click();
      await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
      await page.getByRole("button", { name: "Pause", exact: true }).click();
    } else {
      // Close the selector if score isn't available
      await page.keyboard.press("Escape");
    }
  });

  // ── Breakdown ────────────────────────────────────────────────────────
  await test.step("breakdown", async () => {
    await page.getByRole("tab", { name: "Breakdown" }).click();
    // Verify analysis insights are present — "Key" confirms the factual context ran.
    await expect(page.getByText("Key", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
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
    const targetMeasure = measures.nth(2);
    const targetBox = await targetMeasure.boundingBox();
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

    // Score source swap (conditional — may not be available)
    await openSourceSelector(page);
    const scoreRenditionOption = page.getByRole("option", { name: "Score", exact: true });
    if (await scoreRenditionOption.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await scoreRenditionOption.click();
      await expect(await listeningTo(page, "Score")).toBeVisible();
      await expectPositionPreserved(page, positionBeforeSourceSwap);
    } else {
      await page.keyboard.press("Escape");
    }

    // A/B comparison
    await page.getByRole("button", { name: "Compare", exact: true }).click();
    await expect(page.getByRole("group", { name: "Compare playback sources" })).toBeVisible();

    // Use Transcription for B side since Score may not be available.
    // The helper is idempotent because compare already defaults B to it.
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
    await expect(page.getByRole("button", { name: "Loop selection" })).toBeVisible();

    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
    await expect(
      page.locator('[data-testid="piano-roll"] svg >> rect[fill="var(--accent)"][fill-opacity="0.1"]'),
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
    // Score may not be available if rendering failed
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
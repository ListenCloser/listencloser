import { expect, test, type Page } from "@playwright/test";
import { argosScreenshot } from "@argos-ci/playwright";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

/**
 * EXPERIMENT ONLY — #1143 Option A.
 *
 * This file deliberately changes no production component/CSS. It applies a
 * scoped browser-only stylesheet to the real mocked workspace so visual review
 * can judge the Ableton-operation / authored-music-tool hypothesis using real
 * product content before any production styling decision is made.
 *
 * No fake musical evidence is introduced. Existing Waveform/Piano Roll/Score/
 * Spectrogram components and the normal mock Work remain the rendered source.
 */

async function installMockSession(page: Page) {
  await page.addInitScript(persistSessionScript(), {
    projectRef: MOCK_PROJECT_REF,
    session: mockSession,
  });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
}

async function openDesktopWorkspace(page: Page) {
  await installMockSession(page);
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Breakdown" })).toBeVisible();
}

async function openCompactWorkspace(page: Page) {
  await installMockSession(page);
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Show library" })).toBeVisible();
  await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
}

const optionAStyles = String.raw`
  :root {
    --oa-bg: #111210;
    --oa-panel: #191a17;
    --oa-panel-raised: #20211d;
    --oa-line: #34362f;
    --oa-line-strong: #505349;
    --oa-text: #ecebdc;
    --oa-muted: #9b9d8f;
    --oa-yellow: #e5c54f;
    --oa-orange: #ef754e;
    --oa-blue: #6b8fd6;
    --oa-green: #7fa66b;
    --oa-cyan: #58aaa8;
    --oa-font: "Arial Narrow", "Helvetica Neue", Arial, system-ui, sans-serif;
  }

  html, body { background: var(--oa-bg) !important; }
  body, button, input, summary { font-family: var(--oa-font) !important; }

  .studio-shell {
    background: var(--oa-bg) !important;
    color: var(--oa-text) !important;
    letter-spacing: 0 !important;
  }

  .studio-header {
    min-height: 36px !important;
    height: 36px !important;
    background: #0d0e0c !important;
    border-bottom: 1px solid var(--oa-line) !important;
    box-shadow: none !important;
  }

  .studio-workspace {
    background: var(--oa-bg) !important;
    gap: 0 !important;
  }

  .studio-library,
  .studio-inspector {
    background: var(--oa-panel) !important;
    border-color: var(--oa-line) !important;
    box-shadow: none !important;
  }

  .studio-library { width: 232px !important; }
  .studio-inspector { width: 326px !important; }

  .studio-canvas-area {
    background: #10110f !important;
    border: 0 !important;
    box-shadow: inset 1px 0 var(--oa-line), inset -1px 0 var(--oa-line) !important;
  }

  .library-work-row,
  .library-work-btn,
  .library-import-btn,
  .piece-source-trigger,
  .transport-play-btn,
  .transport-ctrl,
  .studio-mobile-action,
  .ui-tab {
    border-radius: 2px !important;
    box-shadow: none !important;
  }

  .library-work-row {
    margin: 0 6px !important;
    border: 1px solid transparent !important;
    background: transparent !important;
  }

  .library-work-row.selected {
    background: #24251f !important;
    border-color: var(--oa-line-strong) !important;
  }

  .library-work-btn {
    min-height: 44px !important;
    padding: 6px 8px !important;
    background: transparent !important;
    color: var(--oa-text) !important;
  }

  .library-work-title {
    font-size: 12px !important;
    font-weight: 650 !important;
    color: var(--oa-text) !important;
  }

  .library-work-status,
  .muted,
  .studio-service-label {
    color: var(--oa-muted) !important;
  }

  .library-note-glyph { color: var(--oa-yellow) !important; }

  .ui-tab-strip {
    gap: 0 !important;
    border-bottom: 1px solid var(--oa-line) !important;
  }

  .ui-tab {
    min-height: 32px !important;
    padding: 0 12px !important;
    border: 0 !important;
    border-right: 1px solid var(--oa-line) !important;
    background: var(--oa-panel) !important;
    color: var(--oa-muted) !important;
    font-size: 11px !important;
    font-weight: 650 !important;
    letter-spacing: .02em !important;
  }

  .ui-tab:hover { color: var(--oa-text) !important; background: #22231f !important; }
  .ui-tab.active,
  .ui-tab[data-state="active"] {
    color: var(--oa-text) !important;
    background: #25261f !important;
    box-shadow: inset 0 -2px var(--oa-yellow) !important;
  }

  .waveform-wrap,
  .piano-roll-container,
  .spectrogram-wrap,
  .score-wrap {
    border-radius: 0 !important;
    border-color: var(--oa-line) !important;
    box-shadow: none !important;
  }

  .waveform-ruler,
  .waveform,
  .spectrogram-canvas {
    border-radius: 0 !important;
  }

  .transport-bar {
    min-height: 50px !important;
    height: 50px !important;
    background: #0d0e0c !important;
    border-top: 1px solid var(--oa-line-strong) !important;
    box-shadow: none !important;
    color: var(--oa-text) !important;
  }

  .transport-play-btn {
    width: 32px !important;
    height: 32px !important;
    background: var(--oa-yellow) !important;
    color: #12130f !important;
    border: 0 !important;
  }

  .transport-ctrl,
  .piece-source-trigger {
    background: var(--oa-panel) !important;
    border: 1px solid var(--oa-line) !important;
    color: var(--oa-text) !important;
  }

  .transport-ctrl.active,
  .transport-compare-side.active,
  [aria-pressed="true"] {
    color: var(--oa-yellow) !important;
    border-color: color-mix(in srgb, var(--oa-yellow) 55%, var(--oa-line)) !important;
  }

  .transport-time {
    font-variant-numeric: tabular-nums !important;
    font-size: 11px !important;
    font-weight: 650 !important;
    color: var(--oa-text) !important;
  }

  .transport-seek { accent-color: var(--oa-yellow) !important; }

  .inspector-breakdown,
  .inspector-panel,
  .breakdown-panel {
    background: var(--oa-panel) !important;
    color: var(--oa-text) !important;
  }

  details,
  .inspector-evidence-group,
  .inspector-breakdown-evidence-root {
    border-radius: 0 !important;
    border-color: var(--oa-line) !important;
  }

  summary {
    color: var(--oa-text) !important;
    font-size: 11px !important;
    font-weight: 650 !important;
  }

  h1, h2, h3, h4 {
    font-family: var(--oa-font) !important;
    letter-spacing: -.015em !important;
  }

  button:focus-visible,
  [role="tab"]:focus-visible,
  input:focus-visible,
  summary:focus-visible {
    outline: 2px solid var(--oa-cyan) !important;
    outline-offset: 2px !important;
  }

  @media (max-width: 820px) {
    .studio-header { height: 42px !important; min-height: 42px !important; }
    .studio-mobile-action {
      min-height: 30px !important;
      background: var(--oa-panel) !important;
      border: 1px solid var(--oa-line) !important;
      color: var(--oa-text) !important;
      font-size: 11px !important;
      font-weight: 650 !important;
    }
    .studio-canvas-area { box-shadow: none !important; }
    .transport-bar { min-height: 58px !important; height: 58px !important; }
  }
`;

async function applyOptionA(page: Page) {
  await page.addStyleTag({ content: optionAStyles });
  await page.evaluate(() => {
    const root = document.documentElement;
    // Re-map the existing product tokens so mounted representation components
    // can participate in the experiment without changing their implementation.
    root.style.setProperty("--bg", "#111210");
    root.style.setProperty("--panel", "#191a17");
    root.style.setProperty("--panel-2", "#20211d");
    root.style.setProperty("--text", "#ecebdc");
    root.style.setProperty("--muted", "#9b9d8f");
    root.style.setProperty("--border", "#34362f");
    root.style.setProperty("--accent", "#e5c54f");
    root.style.setProperty("--score-playback", "#58aaa8");
    root.style.setProperty("--color-rhythm", "#e5c54f");
    root.style.setProperty("--color-harmony", "#7fa66b");
    root.style.setProperty("--color-theory", "#6b8fd6");
  });
}

test("Option A — professional listening instrument — desktop waveform", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openDesktopWorkspace(page);
  await applyOptionA(page);
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await argosScreenshot(page, "option-a-professional-listening-instrument-waveform", { fullPage: true });
});

test("Option A — professional listening instrument — piano roll", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openDesktopWorkspace(page);
  await applyOptionA(page);
  await page.getByRole("tab", { name: "Piano Roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
  await argosScreenshot(page, "option-a-professional-listening-instrument-piano-roll", { fullPage: true });
});

test("Option A — professional listening instrument — evidence open", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openDesktopWorkspace(page);
  await applyOptionA(page);
  const evidenceRoot = page.locator("details.inspector-breakdown-evidence-root").first();
  if (await evidenceRoot.count()) {
    await evidenceRoot.locator(":scope > summary").click();
  }
  await argosScreenshot(page, "option-a-professional-listening-instrument-evidence", { fullPage: true });
});

test("Option A — professional listening instrument — phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openCompactWorkspace(page);
  await applyOptionA(page);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await argosScreenshot(page, "option-a-professional-listening-instrument-phone", { fullPage: true });
});

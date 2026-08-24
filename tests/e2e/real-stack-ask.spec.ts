import { expect, test } from "@playwright/test";
import { readFileSync, existsSync } from "node:fs";

/**
 * Real-stack Ask inspector test.
 *
 * Uses pre-processed work from global setup. Only the Ask network call is
 * mocked (a real LLM provider isn't configured); everything else runs
 * against the real stack.
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

const SHOTS = process.env.SCREENSHOT_DIR ?? "docs/pr/227";

test("Ask inspects the real workspace: open → answer → switch modes → collapse", async ({ page }) => {
  const setup = loadSetup();
  test.skip(!setup, "global setup did not produce /tmp/real-stack-setup.json");

  let failAsk = false;

  await page.setViewportSize({ width: 1440, height: 900 });
  await injectAuth(page, setup!);

  // Mock only the Ask network call
  await page.route("**/api/v1/ask", (route) => {
    if (failAsk) {
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "Ask is unavailable" }),
      });
      return;
    }
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "This passage stays on the tonic with a gentle stepwise descent.",
        references: [
          { type: "time", start: 2, end: 6, domain: "performance" },
          { type: "measure", start: 1, end: 3 },
        ],
        suggestedActions: [
          { type: "show_representation", representationId: "score" },
          { type: "loop", start: 2, end: 6, domain: "performance" },
          { type: "seek", seconds: 2, domain: "performance" },
        ],
      }),
    });
  });

  await page.goto("/");

  // Wait for pre-processed work to load
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Operation failed")).not.toBeVisible();

  // ── 1. Ask empty state over the whole piece ────────────────────────────
  await page.getByRole("tab", { name: "Ask" }).click();
  await expect(page.getByPlaceholder("Ask about this piece…")).toBeVisible();
  await expect(page.getByText("Whole piece")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/ask-01-whole-piece.png` });

  // ── 2. Ask empty state scoped to a selection ───────────────────────────
  await page.getByRole("tab", { name: "Waveform" }).click();
  const canvas = page.getByTestId("waveform-canvas");
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  if (!box) throw new Error("waveform canvas not found");
  await page.mouse.move(box.x + box.width * 0.2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2, { steps: 5 });
  await page.mouse.up();
  await page.getByRole("tab", { name: "Ask" }).click();
  await expect(page.locator(".ask-context-value")).not.toHaveText("Whole piece");
  await page.screenshot({ path: `${SHOTS}/ask-02-selection-empty.png` });

  // ── Playback continues through the mode switch ─────────────────────────
  await selectSource(page, "Original");
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
  const posPlaying = await transportPosition(page);
  await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThanOrEqual(posPlaying);

  await page.getByRole("tab", { name: "Analysis" }).click();
  await expect(page.getByRole("tab", { name: "Analysis" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
  const posInAnalysis = await transportPosition(page);
  await page.getByRole("tab", { name: "Ask" }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
  await expect.poll(() => transportPosition(page), { timeout: 10_000 }).toBeGreaterThanOrEqual(posInAnalysis);
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // ── 3. Ask an actual question → answer with evidence references ────────
  await page.getByRole("button", { name: "What is happening harmonically here?" }).click();
  await expect(page.getByText("What is happening harmonically here?")).toBeVisible();
  await expect(page.getByText(/This passage stays on the tonic/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Evidence")).toBeVisible();
  await expect(page.getByText("0:02–0:06")).toBeVisible();
  await expect(page.getByText("Measures 1–3")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/ask-03-answer-references.png` });

  // ── 4. Suggested actions render as chips ───────────────────────────────
  await expect(page.getByRole("button", { name: "Open Score" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Loop passage" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Jump to time" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/ask-04-answer-actions.png` });

  // ── 5. Error state ─────────────────────────────────────────────────────
  failAsk = true;
  await page.getByPlaceholder("Ask about this piece…").fill("What key is this passage in?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/not available right now/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/ask-05-error.png` });
  failAsk = false;

  // ── Representation/transport state stays intact after Ask ──────────────
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Ask" }).click();
  await expect(page.getByText(/This passage stays on the tonic/)).toBeVisible();

  // ── Collapse/reopen preserves the Ask conversation ─────────────────────
  await page.getByRole("button", { name: "Hide analysis" }).click();
  await expect(page.locator(".inspector")).toHaveCount(0);
  await page.getByRole("button", { name: "Show analysis" }).click();
  await expect(page.locator(".inspector")).toBeVisible();
  await expect(page.getByText(/This passage stays on the tonic/)).toBeVisible();

  // ── 6. Narrow width: the Ask drawer renders with a backdrop ────────────
  await page.setViewportSize({ width: 768, height: 900 });
  await expect(page.locator(".studio-inspector-backdrop")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/This passage stays on the tonic/)).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/ask-06-narrow-drawer.png` });
});

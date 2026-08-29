import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

/**
 * Contextual Ask inspector UI (MSW).
 *
 * Runs against the MSW mock for the POST /api/v1/ask endpoint so the suite is
 * deterministic and does not require a real LLM provider. This spec proves the
 * Ask mode is a real, frontend-only UI against that mock: conversation,
 * evidence chips, safe reference resolution, and disabled cross-domain
 * actions/references.
 */
test.describe("contextual Ask inspector (MSW)", () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(60_000);
    await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
    await page.goto("/");
    await page.waitForFunction(
      () => navigator.serviceWorker?.controller !== null,
      undefined,
      { timeout: 15_000 },
    );
  });

  async function transportPos(page: import("@playwright/test").Page): Promise<number> {
    return Number(await page.getByRole("slider", { name: "Playback position" }).inputValue());
  }

  async function openAsk(page: import("@playwright/test").Page) {
    await page.getByRole("tab", { name: "Ask" }).click();
    await expect(page.getByRole("tab", { name: "Ask", selected: true })).toBeVisible();
    await expect(page.getByPlaceholder("Ask a question about this recording…")).toBeVisible();
  }

  async function askGroundedStarter(page: import("@playwright/test").Page): Promise<string> {
    const starter = page.locator(".ask-prompt").first();
    await expect(starter).toBeVisible();
    const prompt = (await starter.textContent())?.trim() ?? "";
    expect(prompt).not.toBe("");
    await starter.click();
    return prompt;
  }

  test("Ask answers a grounded starter and renders evidence chips and suggested actions", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    await openAsk(page);
    await expect(
      page.getByText("Questions are grounded in analysis currently available for this recording and selection."),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Explain the harmony in plain language." })).toHaveCount(0);

    const prompt = await askGroundedStarter(page);

    // The user turn and the assistant answer appear; the answer references
    // evidence chips (time, measures, notes, insight).
    await expect(page.getByText(prompt)).toBeVisible();
    await expect(page.getByText(/This passage stays centered on the tonic/)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Evidence")).toBeVisible();
    await expect(page.getByText("0:04–0:08")).toBeVisible();
    await expect(page.getByText("Measures 2–4")).toBeVisible();
    await expect(page.getByText("Notes (2)")).toBeVisible();
    await expect(page.getByText("Key: A minor")).toBeVisible();

    // Suggested actions render as chips.
    await expect(page.getByRole("button", { name: "Open Score" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Loop passage" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Jump to time" })).toBeVisible();

    // The conversation survives a representation switch (Ask stays intact).
    await page.getByRole("tab", { name: "Piano Roll" }).click();
    await expect(page.getByTestId("piano-roll")).toBeVisible({ timeout: 20_000 });
    await openAsk(page);
    await expect(page.getByText(/This passage stays centered on the tonic/)).toBeVisible();
    await expect(page.getByText(prompt)).toBeVisible();
  });

  test("measure reference opens the Score and show_representation opens the matching view", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    await openAsk(page);
    await askGroundedStarter(page);
    await expect(page.getByText(/This passage stays centered on the tonic/)).toBeVisible({ timeout: 10_000 });

    // ── Measure reference opens the Score, session preserved ───────────────
    await page.getByRole("button", { name: "Measures 2–4" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();

    // ── show_representation action opens the correct representation ────────
    await openAsk(page);
    await page.getByRole("button", { name: "Open Score" }).click();
    await expect(page.locator(".sheet-music-container")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");
  });

  test("domain-mismatched loop and seek actions are disabled", async ({ page }) => {
    await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

    // Switch the playback source to the Score so the active timeline
    // is notation time. The mocked suggested actions are performance-domain,
    // so Loop passage and Jump to time must render disabled (not clickable
    // no-ops), while the representation action stays enabled.
    await page.getByRole("button", { name: /Playback source:/ }).click();
    await page.getByRole("option", { name: "Score", exact: true }).click();
    await expect(page.getByRole("button", { name: "Playback source: Score", exact: true })).toBeVisible();

    await openAsk(page);
    await askGroundedStarter(page);
    await expect(page.getByText(/This passage stays centered on the tonic/)).toBeVisible({ timeout: 10_000 });

    const toggleLoop = page.getByRole("button", { name: "Toggle loop" });
    const loopPressedBefore = (await toggleLoop.getAttribute("aria-pressed")) === "true";

    await expect(page.getByRole("button", { name: "Jump to time" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Loop passage" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Open Score" })).toBeEnabled();

    // The disabled state is stable: no transport change happens while in it.
    const posBefore = await transportPos(page);
    await expect.poll(() => transportPos(page)).toBe(posBefore);
    if (loopPressedBefore) {
      await expect(toggleLoop).toHaveAttribute("aria-pressed", "true");
    }
  });
});

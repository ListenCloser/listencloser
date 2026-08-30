import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("a persisted work reopens with synchronized musical workspace views", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );

  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

  // The playback sources are human labels, never internal artifact ids.
  await expect(page.getByRole("button", { name: /Playback source:/ })).toBeVisible();
  await expect(page.getByRole("option", { name: "Original", exact: true })).not.toBeVisible();
  await page.getByRole("button", { name: /Playback source:/ }).click();
  await expect(page.getByRole("option", { name: "Original", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "Transcription", exact: true })).toBeVisible();

  // The four representations are discoverable from the tab bar.
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await page.getByRole("tab", { name: "Piano Roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible();
  await expect(page.getByText(/42 notes/)).toBeVisible();
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible();
  await page.getByRole("tab", { name: "Breakdown" }).click();
  await expect(page.getByText("A minor", { exact: true })).toBeVisible();
  await expect(page.getByText("112 BPM", { exact: true })).toBeVisible();
});

test("import starts one durable understand job and reloads the persisted work", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  const importButton = page.getByRole("complementary").getByRole("button", { name: "Import audio" });
  await expect(importButton).toBeVisible({ timeout: 20_000 });

  await importButton.click();
  await page.getByRole("button", { name: /Upload recording/ }).click();
  const realAudio = process.env.REAL_AUDIO_FILE;
  await page.locator('input[type="file"]').setInputFiles(
    realAudio && existsSync(realAudio)
      ? realAudio
      : { name: "fixture.m4a", mimeType: "audio/mp4", buffer: Buffer.from("mock m4a payload") },
  );

  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByRole("button", { name: /Playback source:/ })).toBeVisible({
    timeout: 20_000,
  });
});

test("score appears as a playback source and follows the transport", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

  // A notation-derived render exists, so Score is a selectable playback source.
  await page.getByRole("button", { name: /Playback source:/ }).click();
  await expect(page.getByRole("option", { name: "Score", exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible();

  await page.getByRole("button", { name: /Playback source:/ }).click();
  await page.getByRole("option", { name: "Score", exact: true }).click();
  await expect(page.getByRole("button", { name: "Playback source: Score", exact: true })).toBeVisible();
});

test("the representation changes independently of the playback source", async ({
  page,
}) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

  // Settle on the original as the source, then keep listening to it
  // while moving between representations.
  const listeningTrigger = page.getByRole("button", { name: /Playback source:/ });
  await listeningTrigger.click();
  await page.getByRole("option", { name: "Original", exact: true }).click();
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Piano Roll" }).click();
  await expect(page.getByTestId("piano-roll")).toBeVisible();
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible();
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Breakdown" }).click();
  await expect(page.getByText("A minor", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();
});

test("compare mode toggles A/B at the same playhead without changing the view", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });

  // Settle on the original source and open the Score representation.
  const listeningTrigger = page.getByRole("button", { name: /Playback source:/ });
  await listeningTrigger.click();
  await page.getByRole("option", { name: "Original", exact: true }).click();
  await page.getByRole("tab", { name: "Score" }).click();
  await expect(page.locator(".sheet-music-container")).toBeVisible();

  // Enter compare: A is Original, B defaults to Transcription.
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("group", { name: "Compare playback sources" })).toBeVisible();
  await expect(page.getByRole("button", { name: "A compare source", exact: true })).toContainText("Original");
  await expect(page.getByRole("button", { name: "B compare source", exact: true })).toContainText("Transcription");

  // Toggle to B: the representation must stay open and the source must switch.
  await page.getByRole("button", { name: "B", exact: true }).click();
  await expect(page.getByRole("button", { name: "B", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".sheet-music-container")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Score" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: "B compare source", exact: true })).toContainText("Transcription");

  // Toggle back to A.
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByRole("button", { name: "A", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "A compare source", exact: true })).toContainText("Original");
  await expect(page.getByRole("button", { name: "B compare source", exact: true })).toContainText("Transcription");

  // Exit compare keeps the active source and the Score view.
  await page.getByRole("button", { name: "Exit compare", exact: true }).click();
  await expect(page.getByRole("group", { name: "Compare playback sources" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();
  await expect(page.locator(".sheet-music-container")).toBeVisible();
});

test("signed-out users see the sign-in gate, not the importer", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => navigator.serviceWorker?.controller !== null, undefined, { timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Import audio" })).not.toBeVisible();
});

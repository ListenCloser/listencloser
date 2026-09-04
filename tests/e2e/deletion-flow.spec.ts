import { expect, test, type Page } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

async function openWorkspace(page: Page) {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
}

test("deleting the active work clears it and leaves no stale transport state", async ({ page }) => {
  await openWorkspace(page);

  const deleteButton = page.getByRole("button", { name: "Delete Test Work" });
  await expect(deleteButton).not.toHaveAttribute("title");
  await deleteButton.hover();
  await expect(page.getByRole("tooltip", { name: "Delete recording" })).toBeVisible();
  await deleteButton.click();

  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toHaveCount(0);
  await expect(page.getByText("No recordings yet", { exact: true })).toBeVisible();
  const emptyWorkspace = page.locator(".piece-empty-v3");
  await expect(emptyWorkspace.getByRole("heading", { name: "Import a recording" })).toBeVisible();
  await expect(emptyWorkspace.getByRole("button", { name: "Import audio" })).toBeVisible();

  // The old bespoke first-run illustration remains in legacy markup only until
  // #523 deletes that owner; the accepted interface foundation keeps it inert.
  await expect(page.getByTestId("empty-workspace-signal")).toBeHidden();
  await expect(page.getByText("Move through waveform, notes, notation, and evidence without losing your place.", { exact: true })).toBeHidden();

  // Processing is import policy, so the Library owns both transcription and
  // score reconstruction choices even when the main workspace is empty.
  const library = page.locator("aside.studio-library");
  await library.getByText("Processing", { exact: true }).click();
  const autoMode = library.getByRole("button", { name: "Auto", exact: true });
  await expect(autoMode).not.toHaveAttribute("title");
  await autoMode.hover();
  await expect(page.getByRole("tooltip", { name: "General and mixed recordings" })).toBeVisible();
  await expect(autoMode).toHaveAttribute("aria-describedby");

  const pm2sMode = library.getByRole("button", { name: "PM2S", exact: true });
  await expect(pm2sMode).not.toHaveAttribute("title");
  await pm2sMode.hover();
  await expect(page.getByRole("tooltip", { name: "Experimental learned piano score reconstruction" })).toBeVisible();
  await expect(pm2sMode).toHaveAttribute("aria-describedby");

  await expect(page.getByRole("slider", { name: "Playback position" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Playback source:/ })).toHaveCount(0);
});

test("failed active-work deletion restores the selected workspace and playback", async ({ page }) => {
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = input instanceof Request ? input.method : init?.method;
      const url = input instanceof Request ? input.url : String(input);
      if (method === "DELETE" && url.includes("/api/v1/works/mock-work-1")) {
        return new Response(JSON.stringify({ error: "forced delete failure" }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        });
      }
      return originalFetch(input, init);
    };
  });

  await openWorkspace(page);
  await page.getByRole("button", { name: "Delete Test Work" }).click();

  await expect(page.locator(".library-error")).toHaveText("Delete failed. The recording was restored.");
  const restoredWork = page.getByRole("button", { name: /^Test Work\b/ });
  await expect(restoredWork).toBeVisible();
  await expect(restoredWork).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: /Playback source:/ })).toBeVisible();
});

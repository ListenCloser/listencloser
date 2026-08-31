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

  // The icon-only destructive action gets deliberate help rather than a
  // browser-native title bubble. Side placement keeps that help inside the
  // narrow Library rail instead of pushing it into the scroll boundary.
  const deleteButton = page.getByRole("button", { name: "Delete Test Work" });
  await expect(deleteButton).not.toHaveAttribute("title");
  await deleteButton.hover();
  await expect(page.getByRole("tooltip", { name: "Delete recording" })).toBeVisible();

  // Delete is a direct row action. A one-command overflow menu added friction
  // on desktop and was effectively hidden behind hover on touch devices.
  await deleteButton.click();

  // The query-backed mutation removes the row optimistically while both the
  // Library and Canvas move to their real empty states.
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toHaveCount(0);
  await expect(page.getByText("No recordings yet", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Import a recording" })).toBeVisible();

  // The first-use visual is a truthful structural scaffold, not generic music
  // clip-art or fake waveform/analysis data.
  const emptySignal = page.getByTestId("empty-workspace-signal");
  await expect(emptySignal).toBeVisible();
  await expect(emptySignal).toHaveAttribute("aria-hidden", "true");
  await expect(page.getByText("Move through waveform, notes, notation, and evidence without losing your place.", { exact: true })).toBeVisible();
  await expect(page.locator(".empty-note, .empty-staff-line")).toHaveCount(0);

  // Terse transcription modes explain the model choice deliberately. Visible
  // control copy stays unchanged and the help is linked via aria-describedby.
  await page.getByText("Transcription", { exact: true }).last().click();
  const autoMode = page.getByRole("button", { name: "Auto", exact: true }).last();
  await expect(autoMode).not.toHaveAttribute("title");
  await autoMode.hover();
  await expect(page.getByRole("tooltip", { name: "Best default for most recordings" })).toBeVisible();
  await expect(autoMode).toHaveAttribute("aria-describedby");

  // No stale transport state: deleting the active work removes the source
  // controls entirely rather than leaving a disabled playhead behind.
  await expect(page.getByRole("slider", { name: "Playback position" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Playback source:/ })).toHaveCount(0);
});

test("failed active-work deletion restores the selected workspace and playback", async ({ page }) => {
  // openapi-fetch captures its fetch implementation when the generated client
  // is created. Install this browser fault boundary before navigation so both
  // generated fetch(Request) calls and legacy fetch(url, init) calls see the
  // same forced failure without coupling the product assertion to one client.
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

  // Successful GETs still flow through MSW, so the restored active work must
  // genuinely reload its bundle and playback sources rather than merely
  // reappearing in the optimistic works cache.
  await page.getByRole("button", { name: "Delete Test Work" }).click();

  await expect(page.locator(".library-error")).toHaveText("Delete failed. The recording was restored.");
  const restoredWork = page.getByRole("button", { name: /^Test Work\b/ });
  await expect(restoredWork).toBeVisible();
  await expect(restoredWork).toHaveAttribute("aria-current", "true");

  // Restoring the row alone is not enough. The local workspace transaction
  // must also roll back so HomeContent reloads the work and rebuilds transport.
  await expect(page.getByRole("slider", { name: "Playback position" })).toBeEnabled({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: /Playback source:/ })).toBeVisible();
});

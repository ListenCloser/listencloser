import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

test("local import forwards files above the former 4 MiB browser ceiling", async ({ page }) => {
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
  await page.reload();

  // This fixture opens an existing Work, so the empty-import helper is not
  // visible here. The product contract we care about is still global: no
  // loaded workspace may advertise or enforce the removed 4 MiB ceiling.
  await expect(page.getByText(/up to 4 MB|4 MiB/i)).toHaveCount(0);

  const fileInput = page.locator("#audio-import-input");
  await expect(fileInput).toHaveCount(1, { timeout: 20_000 });
  await fileInput.setInputFiles({
    name: "former-browser-limit.m4a",
    mimeType: "audio/mp4",
    // One byte above the historical 4 MiB veto is sufficient to prove the
    // browser no longer rejects a file that the authoritative contract accepts.
    buffer: Buffer.alloc(4 * 1024 * 1024 + 1),
  });

  await expect(page.getByText("Ready to listen.", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/Audio files must be 4 MB/i)).toHaveCount(0);
});

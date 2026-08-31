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

  // The client advertises formats only. Size enforcement belongs to the signed
  // upload-intent/backend contract so this surface cannot drift from Storage.
  await expect(
    page.getByText("WAV, MP3, M4A, FLAC, OGG, AAC", { exact: true }),
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/up to 4 MB|4 MiB/i)).toHaveCount(0);

  const fileInput = page.locator("#audio-import-input");
  await expect(fileInput).toHaveCount(1);
  await fileInput.setInputFiles({
    name: "former-browser-limit.m4a",
    mimeType: "audio/mp4",
    // One byte above the historical 4 MiB veto is sufficient to prove the
    // browser no longer rejects a file that the authoritative contract accepts.
    buffer: Buffer.alloc(4 * 1024 * 1024 + 1),
  });

  await expect(page.getByText("Recording saved.", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/Audio files must be 4 MB/i)).toHaveCount(0);
});

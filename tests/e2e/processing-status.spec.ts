import { expect, test, type Page } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

async function startProcessing(page: Page, filename: string) {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  await page.reload();

  const importButton = page.getByRole("complementary").getByRole("button", { name: "Import audio" });
  if (!(await importButton.isVisible())) {
    const showLibrary = page.getByRole("button", { name: "Show library" });
    await expect(showLibrary).toBeVisible({ timeout: 5_000 });
    await showLibrary.click();
  }
  await expect(importButton).toBeVisible({ timeout: 20_000 });
  await expect(importButton).toBeEnabled({ timeout: 10_000 });
  await importButton.click();
  await page.locator('input[type="file"]').setInputFiles({
    name: filename,
    mimeType: "audio/mp4",
    buffer: Buffer.from("mock processing status payload"),
  });

  const notice = page.locator(".workspace-processing-notice");
  await expect(page.getByText("Recording saved.", { exact: true })).toBeVisible({ timeout: 5_000 });
  await expect(notice).toBeVisible();
  return notice;
}

test("processing stays compact and cancellation preserves the saved workspace", async ({ page }) => {
  const notice = await startProcessing(page, "compact-progress.m4a");
  const cancel = notice.getByRole("button", { name: "Cancel" });
  await expect(cancel).toBeVisible();

  const noticeBox = await notice.boundingBox();
  const cancelBox = await cancel.boundingBox();
  expect(noticeBox).not.toBeNull();
  expect(cancelBox).not.toBeNull();
  expect(noticeBox!.width).toBeLessThanOrEqual(500);
  expect(noticeBox!.height).toBeLessThanOrEqual(160);
  expect(cancelBox!.width).toBeLessThanOrEqual(120);
  expect(cancelBox!.height).toBeLessThanOrEqual(44);

  await cancel.click();
  await expect(notice).not.toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.locator(".operation-layer")).not.toBeVisible();
});

test("processing status remains bounded on a phone-sized viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const notice = await startProcessing(page, "mobile-progress.m4a");
  const cancel = notice.getByRole("button", { name: "Cancel" });
  await expect(cancel).toBeVisible();

  const noticeBox = await notice.boundingBox();
  const cancelBox = await cancel.boundingBox();
  expect(noticeBox).not.toBeNull();
  expect(cancelBox).not.toBeNull();
  expect(noticeBox!.x).toBeGreaterThanOrEqual(0);
  expect(noticeBox!.x + noticeBox!.width).toBeLessThanOrEqual(390);
  expect(noticeBox!.height).toBeLessThanOrEqual(160);
  expect(cancelBox!.height).toBeLessThanOrEqual(44);
});

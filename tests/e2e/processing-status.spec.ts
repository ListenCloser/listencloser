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

  // This spec owns processing-notice behavior, not Library responsive chrome.
  // The durable hidden input is the actual import boundary and is present in
  // HomeContent at every workspace width, so drive it directly instead of
  // making this regression depend on whether the Library drawer is expanded.
  const fileInput = page.locator("#audio-import-input");
  await expect(fileInput).toHaveCount(1, { timeout: 20_000 });
  await fileInput.setInputFiles({
    name: filename,
    mimeType: "audio/mp4",
    buffer: Buffer.from("mock processing status payload"),
  });

  const notice = page.locator(".workspace-processing-notice");
  await expect(page.getByText("Recording saved.", { exact: true })).toBeVisible({ timeout: 5_000 });
  await expect(notice).toBeVisible();
  return notice;
}

test("processing uses a bottom status shelf and cancellation preserves the saved workspace", async ({ page }) => {
  const notice = await startProcessing(page, "compact-progress.m4a");
  const cancel = notice.getByRole("button", { name: "Cancel" });
  await expect(cancel).toBeVisible();

  const noticeBox = await notice.boundingBox();
  const cancelBox = await cancel.boundingBox();
  const workspaceBox = await page.locator(".studio-workspace-v3").boundingBox();
  const transportBox = await page.locator(".transport-bar-v3").boundingBox();
  expect(noticeBox).not.toBeNull();
  expect(cancelBox).not.toBeNull();
  expect(workspaceBox).not.toBeNull();
  expect(transportBox).not.toBeNull();

  // The status is a reserved row between the workspace and transport, not a
  // floating card over the representation.
  expect(noticeBox!.height).toBeLessThanOrEqual(44);
  expect(Math.abs(noticeBox!.y - (workspaceBox!.y + workspaceBox!.height))).toBeLessThanOrEqual(1);
  expect(Math.abs(transportBox!.y - (noticeBox!.y + noticeBox!.height))).toBeLessThanOrEqual(1);
  expect(cancelBox!.width).toBeLessThanOrEqual(120);
  expect(cancelBox!.height).toBeLessThanOrEqual(36);

  // Normal desktop workspace has no empty global header row.
  await expect(page.locator(".studio-header-v3")).toBeHidden();

  await cancel.click();
  await expect(notice).not.toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.locator(".operation-layer")).not.toBeVisible();
});

test("processing status remains bounded and preserves mobile workspace controls", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const notice = await startProcessing(page, "mobile-progress.m4a");
  const cancel = notice.getByRole("button", { name: "Cancel" });
  await expect(cancel).toBeVisible();
  await expect(page.locator(".studio-header-v3")).toBeVisible();

  const noticeBox = await notice.boundingBox();
  const cancelBox = await cancel.boundingBox();
  const workspaceBox = await page.locator(".studio-workspace-v3").boundingBox();
  const transportBox = await page.locator(".transport-bar-v3").boundingBox();
  expect(noticeBox).not.toBeNull();
  expect(cancelBox).not.toBeNull();
  expect(workspaceBox).not.toBeNull();
  expect(transportBox).not.toBeNull();
  expect(noticeBox!.x).toBeGreaterThanOrEqual(0);
  expect(noticeBox!.x + noticeBox!.width).toBeLessThanOrEqual(390);
  expect(noticeBox!.height).toBeLessThanOrEqual(54);
  expect(Math.abs(noticeBox!.y - (workspaceBox!.y + workspaceBox!.height))).toBeLessThanOrEqual(1);
  expect(Math.abs(transportBox!.y - (noticeBox!.y + noticeBox!.height))).toBeLessThanOrEqual(1);
  expect(cancelBox!.height).toBeLessThanOrEqual(36);
});

import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { dismissWorkspaceNotice, injectAuth } from "./real-stack-auth";

const REAL_AUDIO = process.env.REAL_AUDIO_FILE;
const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

async function importSource(page: import("@playwright/test").Page) {
  await expect(
    page.getByRole("complementary").getByRole("button", { name: "Import audio" }),
  ).toBeEnabled({ timeout: 30_000 });
  await page.getByRole("complementary").getByRole("button", { name: "Import audio" }).click();
  await page.getByRole("menuitem", { name: /Upload recording/ }).click();
  await expect(page.getByRole("dialog", { name: "Process recording" })).toBeVisible();

  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Choose audio" }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles(REAL_AUDIO!);

  await expect(
    page.getByRole("button", { name: "Playback source: Original", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
}

test("production / space runs opt-in through the real worker and persists exact provenance", async ({ page }) => {
  test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required");
  test.skip(!existsSync(REAL_AUDIO!), `REAL_AUDIO_FILE does not exist: ${REAL_AUDIO}`);
  test.skip(!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY, "local Supabase env not configured");

  await injectAuth(page);
  await page.goto("/");
  await dismissWorkspaceNotice(page);
  await importSource(page);

  await expect(page.getByRole("tab", { name: "Breakdown" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("tab", { name: "Breakdown" }).click();

  const inspector = page.locator("aside.inspector");
  const lens = inspector.getByRole("region", { name: "Production and spatial analysis" });
  await expect(lens).toBeVisible({ timeout: 30_000 });
  await lens.getByRole("button", { name: "Add analysis" }).click();
  await expect(lens.getByText("Production / Space", { exact: true })).toBeVisible();
  await expect(lens.getByText("Experimental", { exact: true })).toBeVisible();
  await lens.getByRole("button", { name: "Add", exact: true }).click();

  await expect(lens.getByText("Spectral centroid", { exact: true })).toBeVisible({ timeout: 300_000 });
  await expect(lens.getByText("Onset strength", { exact: true })).toBeVisible();
  await expect(lens.getByText(/Mid\/side evidence is unavailable|Side energy share/)).toBeVisible();

  const spectral = lens.locator("article").filter({ hasText: "Spectral centroid" });
  await spectral.getByText("Method", { exact: true }).click();
  await expect(spectral.getByText(/librosa spectral centroid mean per fixed window/)).toBeVisible();
  await expect(spectral.getByText(/Source Version:/)).toBeVisible();

  await spectral.getByRole("button", { name: "Inspect", exact: true }).click();
  await expect(inspector.getByRole("button", { name: "Clear selection" })).toBeVisible({ timeout: 10_000 });

  await page.reload();
  await dismissWorkspaceNotice(page);
  await expect(page.getByRole("tab", { name: "Breakdown" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("tab", { name: "Breakdown" }).click();
  const reloadedLens = page
    .locator("aside.inspector")
    .getByRole("region", { name: "Production and spatial analysis" });
  await expect(reloadedLens.getByText("Spectral centroid", { exact: true })).toBeVisible({ timeout: 30_000 });
});

import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { injectAuth, dismissWorkspaceNotice } from "./real-stack-auth";

const REAL_AUDIO = process.env.REAL_AUDIO_FILE;
const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

type JsonRow = Record<string, unknown>;

async function serviceRows(path: string): Promise<JsonRow[]> {
  const response = await fetch(`${SUPABASE_URL!.replace(/\/$/, "")}/rest/v1/${path}`, {
    headers: {
      apikey: SERVICE_KEY!,
      Authorization: `Bearer ${SERVICE_KEY!}`,
    },
  });
  if (!response.ok) {
    throw new Error(`Supabase service query failed (${response.status}): ${await response.text()}`);
  }
  return await response.json() as JsonRow[];
}

async function waitForProjectReady(page: import("@playwright/test").Page) {
  await page
    .waitForResponse(
      (resp) =>
        /\/api\/v1\/projects\/[^/]+\/works$/.test(new URL(resp.url()).pathname) &&
        resp.request().method() === "GET",
      { timeout: 30_000 },
    )
    .catch(() => {});
  await expect(
    page.getByRole("complementary").getByRole("button", { name: "Import audio" }),
  ).toBeEnabled({ timeout: 30_000 });
}

async function importWithRetry(page: import("@playwright/test").Page) {
  await waitForProjectReady(page);
  for (let attempt = 0; attempt < 5; attempt++) {
    const importButton = page
      .getByRole("complementary")
      .getByRole("button", { name: "Import audio" });
    await expect(importButton).toBeEnabled({ timeout: 30_000 });
    await importButton.click();
    await page.getByRole("menuitem", { name: /Upload recording/ }).click();
    await page.locator('input[type="file"]').setInputFiles(REAL_AUDIO!);

    const processing = page.getByRole("progressbar");
    const failed = page.getByRole("alert").filter({ hasText: "Your project is still loading" });
    const outcome = await Promise.race([
      processing.waitFor({ state: "visible", timeout: 15_000 }).then(() => "started"),
      failed.waitFor({ state: "visible", timeout: 15_000 }).then(() => "failed"),
    ]);
    if (outcome === "started") return;
    await failed.getByRole("button", { name: "Try another file" }).click();
    await expect(failed).toBeHidden({ timeout: 10_000 });
  }
  throw new Error("PM2S validation import did not start after retries");
}

test("solo-piano PM2S path reaches a rendered, playable Score with durable provenance", async ({ page }) => {
  test.skip(!REAL_AUDIO, "REAL_AUDIO_FILE is required");
  test.skip(!existsSync(REAL_AUDIO!), `REAL_AUDIO_FILE does not exist: ${REAL_AUDIO}`);
  test.skip(!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY, "local Supabase env not configured");

  await injectAuth(page);
  await page.goto("/");
  await waitForProjectReady(page);

  // Exercise the actual product controls added for the experimental route.
  const processingSettings = page.getByText("Processing", { exact: true });
  await expect(processingSettings).toBeVisible();
  await processingSettings.click();

  const transcription = page.getByRole("group", { name: "Transcription mode" });
  const soloPiano = transcription.getByRole("button", { name: "Solo piano", exact: true });
  await soloPiano.click();
  await expect(soloPiano).toHaveAttribute("aria-pressed", "true");

  const scoreInterpretation = page.getByRole("group", { name: "Score interpretation" });
  const pm2s = scoreInterpretation.getByRole("button", { name: "PM2S", exact: true });
  await pm2s.click();
  await expect(pm2s).toHaveAttribute("aria-pressed", "true");

  await importWithRetry(page);
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({ timeout: 480_000 });
  await expect(page.getByText("Operation failed")).not.toBeVisible();
  await dismissWorkspaceNotice(page);

  // Canonical performance evidence still exists independently of score reconstruction.
  await page.getByRole("tab", { name: "Piano Roll" }).click();
  const pianoRoll = page.getByTestId("piano-roll");
  await expect(pianoRoll).toBeVisible({ timeout: 20_000 });
  await expect(pianoRoll.getByText(/\d+ notes/)).toBeVisible();

  // The PM2S-derived score survives MuseScore import and reaches OSMD.
  await page.getByRole("tab", { name: "Score" }).click();
  const score = page.locator(".sheet-music-container");
  await expect(score).toBeVisible({ timeout: 60_000 });
  expect(await score.locator("g.vf-measure").count()).toBeGreaterThan(2);

  // A reconstructed score must also provide the distinct notation-derived playback source.
  await page.getByRole("button", { name: /Playback source:/ }).click();
  await page.getByRole("option", { name: "Score", exact: true }).click();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // Persist a reviewable product artifact even when the run is otherwise green.
  await mkdir("pm2s-validation", { recursive: true });
  await score.screenshot({ path: "pm2s-validation/pm2s-score.png" });

  // Verify the product selection reached durable job and Version identity, not merely local UI state.
  const jobs = await serviceRows("jobs?select=id,stage,parameters,provenance&order=created_at.desc");
  const pm2sJob = jobs.find((row) => {
    const parameters = row.parameters;
    return typeof parameters === "object" && parameters !== null
      && (parameters as JsonRow).score_engine === "pm2s"
      && (parameters as JsonRow).transcription_profile === "solo_piano";
  });
  expect(pm2sJob, "expected a durable solo_piano + pm2s job").toBeTruthy();
  expect(pm2sJob!.stage).toBe("succeeded");

  const versions = await serviceRows("artifact_versions?select=id,label,metadata&order=created_at.asc");
  const pm2sVersions = versions.filter((row) => {
    const metadata = row.metadata;
    return typeof metadata === "object" && metadata !== null
      && (metadata as JsonRow).score_engine_requested === "pm2s";
  });
  expect(pm2sVersions.length).toBeGreaterThanOrEqual(2);
  expect(
    pm2sVersions.some((row) => {
      const metadata = row.metadata as JsonRow;
      const provenance = metadata.provenance;
      return typeof provenance === "object" && provenance !== null
        && (provenance as JsonRow).engine === "pm2s";
    }),
    "expected PM2S engine provenance on a persisted score artifact",
  ).toBe(true);

  console.log(JSON.stringify({
    validation: "pm2s-real-stack",
    job_id: pm2sJob!.id,
    stage: pm2sJob!.stage,
    persisted_pm2s_versions: pm2sVersions.length,
    score_measures: await score.locator("g.vf-measure").count(),
  }));
});

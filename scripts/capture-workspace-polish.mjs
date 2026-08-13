// One-off visual-evidence capture for PR #216 (core workspace polish).
// Drives the real stack at BASE with a fresh account, imports the canonical
// real-piano.m4a, and captures deterministic screenshots of each polished
// state into docs/pr/216/. Before running: build + start the frontend against
// the local Supabase stack and have backend+worker up on :8000.
//
// Usage:
//   SUPABASE_URL=http://127.0.0.1:54321 SUPABASE_ANON_KEY=<key> \
//   SUPABASE_SERVICE_ROLE_KEY=<key> \
//   REAL_AUDIO_FILE=$PWD/tests/fixtures/real-piano.m4a \
//   node scripts/capture-workspace-polish.mjs
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { existsSync } from "node:fs";

const BASE = process.env.BASE_URL || "http://localhost:3000";
const REAL_AUDIO = process.env.REAL_AUDIO_FILE;
const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const VIEWPORT = { width: 1440, height: 1000 };
const OUT_DIR = "docs/pr/216";

if (!REAL_AUDIO || !existsSync(REAL_AUDIO)) throw new Error("REAL_AUDIO_FILE is required and must exist");
if (!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY) throw new Error("Supabase env is required");

function storageKey(url) {
  return `sb-${new URL(url).hostname.split(".")[0]}-auth-token`;
}

async function createSession() {
  const email = `pr216-${Date.now()}@real-stack.test`;
  const password = "real-stack-12345678";
  const created = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: "POST",
    headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, email_confirm: true }),
  });
  const createdBody = await created.json().catch(() => ({}));
  if (!created.ok && createdBody?.code !== "user_already_exists") {
    throw new Error(`failed to create test user: ${created.status} ${JSON.stringify(createdBody)}`);
  }
  const token = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const tokenBody = await token.json();
  if (!tokenBody?.access_token) throw new Error(`failed to sign in: ${token.status}`);
  return tokenBody;
}

mkdirSync(OUT_DIR, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: VIEWPORT });
const shot = (name) => page.screenshot({ path: `${OUT_DIR}/${name}`, type: "png" });

try {
  const auth = await createSession();
  await page.addInitScript(
    ({ key, session }) => {
      window.localStorage.setItem(key, JSON.stringify({
        access_token: session.access_token,
        token_type: "bearer",
        expires_in: 3600,
        expires_at: Math.floor(Date.now() / 1000) + 3600,
        refresh_token: session.refresh_token ?? "",
        user: session.user,
      }));
    },
    { key: storageKey(SUPABASE_URL), session: auth },
  );

  const projectSettled = page.waitForResponse(
    (resp) => resp.url().includes("/api/v1/projects") && resp.request().method() === "POST",
    { timeout: 30_000 },
  ).catch(() => {});
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await projectSettled;

  const importButton = page.getByRole("complementary").getByRole("button", { name: "Import audio" });
  await importButton.waitFor({ timeout: 30_000 });
  await importButton.click();
  await page.locator('input[type="file"]').setInputFiles(REAL_AUDIO);

  // ── Processing / upload state ─────────────────────────────────────────
  await page.locator(".piece-processing-card").waitFor({ timeout: 20_000 });
  await page.waitForTimeout(400);
  await shot("processing-overlay.png");
  console.log("wrote processing-overlay.png");

  await page.getByRole("tab", { name: "Piano roll" }).waitFor({ timeout: 300_000 });

  // ── Listen / waveform (light restyle) while playing ────────────────────
  await page.getByRole("button", { name: "Original", exact: true }).click();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await page.waitForTimeout(4000);
  await page.locator(".piece-active-view .visualizer").waitFor({ timeout: 20_000 });
  await page.locator(".piece-active-view").screenshot({ path: `${OUT_DIR}/listen-waveform.png`, type: "png" });
  console.log("wrote listen-waveform.png");
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // ── Library + work header ──────────────────────────────────────────────
  await page.locator(".piece-desk-heading").screenshot({ path: `${OUT_DIR}/work-header.png`, type: "png" });
  await page.locator(".studio-library").screenshot({ path: `${OUT_DIR}/library.png`, type: "png" });
  console.log("wrote work-header.png, library.png");

  // ── Sparse Analysis ────────────────────────────────────────────────────
  await page.getByRole("tab", { name: "Analysis" }).click();
  await page.locator(".analysis-content").waitFor({ timeout: 20_000 });
  await page.getByText(/confidently|C major|Key/i).first().waitFor({ timeout: 15_000 });
  await page.waitForTimeout(500);
  await page.locator(".piece-active-view").screenshot({ path: `${OUT_DIR}/analysis-sparse.png`, type: "png" });
  console.log("wrote analysis-sparse.png");

  // ── Opening state (deterministic: stall the saved-work bundle) ─────────
  await page.route("**/api/v1/works/*", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    await new Promise((resolve) => setTimeout(resolve, 4000));
    return route.continue();
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator(".piece-loading").waitFor({ timeout: 10_000 });
  await shot("opening-your-music.png");
  console.log("wrote opening-your-music.png");
  await page.unroute("**/api/v1/works/*");
  await page.getByRole("tab", { name: "Listen" }).waitFor({ timeout: 60_000 });

  // ── Delete → optimistic empty state ────────────────────────────────────
  await page.getByTitle("Delete work").click();
  await page.getByTitle("Click again to confirm delete").click();
  await page.locator(".piece-empty").waitFor({ timeout: 15_000 });
  await page.waitForTimeout(250);
  await shot("delete-empty-state.png");
  console.log("wrote delete-empty-state.png");

  console.log("done");
} finally {
  await browser.close();
}
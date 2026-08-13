// One-off visual-evidence capture for PR #214 (piano grand staff).
// Renders the before/after MusicXML for real-piano.m4a via OSMD at a fixed
// viewport and writes PNGs. Usage: node scripts/capture-grand-staff.mjs
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = "http://localhost:8765";
const VIEWPORT = { width: 1440, height: 1000 };
const OUT = [
  "artifacts/score-before.png",
  "artifacts/score-after.png",
];

mkdirSync("artifacts", { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: VIEWPORT });

for (const [name, out] of [
  ["rp_before.xml", OUT[0]],
  ["rp_after.xml", OUT[1]],
]) {
  await page.goto(`${BASE}/render.html?xml=${name}`, { waitUntil: "networkidle" });
  await page.waitForSelector(".sheet-music-container svg", { timeout: 30000 });
  await page.locator(".sheet-music-container").screenshot({ path: out, type: "png" });
  console.log("wrote", out);
}

await browser.close();

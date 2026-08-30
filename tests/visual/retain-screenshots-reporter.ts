import { cp, mkdir, stat } from "node:fs/promises";

const SOURCE_DIR = "screenshots";
const REVIEW_DIR = "visual-review-screenshots";

async function directoryExists(path: string) {
  try {
    return (await stat(path)).isDirectory();
  } catch {
    return false;
  }
}

async function retainScreenshots() {
  if (!process.env.CI || !(await directoryExists(SOURCE_DIR))) return;

  await mkdir(REVIEW_DIR, { recursive: true });
  await cp(SOURCE_DIR, REVIEW_DIR, { recursive: true, force: true });
}

export default class RetainVisualScreenshotsReporter {
  async onTestEnd() {
    // Argos removes its working screenshot directory during its suite-level
    // reporter cleanup. Copy after each test while the exact captured PNGs are
    // still present so hosted upload/quota state cannot erase review evidence.
    await retainScreenshots();
  }

  async onEnd() {
    // Final best-effort flush for reporters/configurations that leave the
    // source directory intact through suite completion.
    await retainScreenshots();
  }
}

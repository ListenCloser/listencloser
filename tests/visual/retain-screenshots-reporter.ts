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

export default class RetainVisualScreenshotsReporter {
  async onEnd() {
    if (!process.env.CI || !(await directoryExists(SOURCE_DIR))) return;

    await mkdir(REVIEW_DIR, { recursive: true });
    await cp(SOURCE_DIR, REVIEW_DIR, { recursive: true });
  }
}

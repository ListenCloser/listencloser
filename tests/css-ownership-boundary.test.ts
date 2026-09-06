import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = process.cwd();
const APP = join(ROOT, "app");

function read(path: string): string {
  return readFileSync(join(ROOT, path), "utf8");
}

describe("global CSS ownership", () => {
  it("does not restore retired global compatibility layers", () => {
    for (const filename of ["workspace-interactions.css", "readiness.css"]) {
      expect(existsSync(join(APP, filename))).toBe(false);
      expect(read("app/layout.tsx")).not.toContain(filename);
    }
  });

  it("keeps migrated component chrome out of the remaining interface bridge", () => {
    const foundation = read("app/interface-foundation.css");
    const retiredFamilies = [
      /\.library-/,
      /\.operation-/,
      /\.piece-(?:desk|loading|empty|active-view|view-tabs|source|processing)-?/,
      /\.representation-toolbar\b/,
      /\.repr-more-/,
      /\.transport-/,
      /\.workspace-(?:notice|processing-notice)\b/,
      /\.ui-tab\b/,
    ];

    for (const pattern of retiredFamilies) {
      expect(foundation).not.toMatch(pattern);
    }
  });
});

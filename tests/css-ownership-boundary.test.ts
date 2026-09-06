import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = process.cwd();
const APP = join(ROOT, "app");

function read(path: string): string {
  return readFileSync(join(ROOT, path), "utf8");
}

describe("global CSS ownership", () => {
  it("does not restore the retired workspace interaction layer", () => {
    expect(existsSync(join(APP, "workspace-interactions.css"))).toBe(false);
    expect(read("app/layout.tsx")).not.toContain("workspace-interactions.css");
  });

  it("keeps migrated component chrome out of the remaining interface bridge", () => {
    const foundation = read("app/interface-foundation.css");
    const retiredFamilies = [
      /\.library-/,
      /\.piece-(?:desk|loading|empty|active-view|view-tabs|source)-?/,
      /\.representation-toolbar\b/,
      /\.repr-more-/,
      /\.transport-/,
      /\.ui-tab\b/,
    ];

    for (const pattern of retiredFamilies) {
      expect(foundation).not.toMatch(pattern);
    }
  });
});

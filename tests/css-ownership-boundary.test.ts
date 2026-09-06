import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = process.cwd();
const APP = join(ROOT, "app");

function read(path: string): string {
  return readFileSync(join(ROOT, path), "utf8");
}

describe("global CSS ownership", () => {
  it("does not restore retired historical styling layers", () => {
    const layout = read("app/layout.tsx");
    const retired = [
      "workspace-v3.css",
      "product-polish-v4.css",
      "workspace-interactions.css",
      "readiness.css",
      "interface-foundation.css",
    ];

    for (const filename of retired) {
      expect(existsSync(join(APP, filename))).toBe(false);
      expect(layout).not.toContain(filename);
    }
  });

  it("keeps root stylesheet imports responsibility-named instead of versioned", () => {
    const layout = read("app/layout.tsx");
    expect(layout).not.toMatch(/import\s+["']\.\/[^"']*-v\d+\.css["']/i);

    for (const filename of [
      "tokens.css",
      "representation-visuals.css",
      "inspector.css",
      "breakdown.css",
      "mobile-workspace.css",
      "landing-product-story.css",
    ]) {
      expect(existsSync(join(APP, filename))).toBe(true);
      expect(layout).toContain(`./${filename}`);
    }
  });
});

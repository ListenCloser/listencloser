import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = process.cwd();
const APP = join(ROOT, "app");

function read(path: string): string {
  return readFileSync(join(ROOT, path), "utf8");
}

function sourceFiles(root: string): string[] {
  return readdirSync(root).flatMap((entry) => {
    const path = join(root, entry);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(?:ts|tsx)$/.test(entry) ? [path] : [];
  });
}

describe("frontend visual ownership", () => {
  it("does not restore retired historical styling layers", () => {
    const layout = read("app/layout.tsx");
    const retired = [
      "workspace-v3.css",
      "product-polish-v4.css",
      "workspace-interactions.css",
      "readiness.css",
      "interface-foundation.css",
      "visual-language.css",
      "inspector.css",
      "breakdown.css",
    ];

    for (const filename of retired) {
      expect(existsSync(join(APP, filename)), filename).toBe(false);
      expect(layout).not.toContain(filename);
    }
  });

  it("keeps the root stylesheet graph small and responsibility-named", () => {
    const layout = read("app/layout.tsx");
    expect(layout).not.toMatch(/import\s+["']\.\/[^"']*-v\d+\.css["']/i);

    const expected = [
      "globals.css",
      "tokens.css",
      "representation-visuals.css",
      "mobile-workspace.css",
      "landing-product-story.css",
    ];

    for (const filename of expected) {
      expect(existsSync(join(APP, filename)), filename).toBe(true);
      expect(layout).toContain(`./${filename}`);
    }

    const rootCssImports = [...layout.matchAll(/import\s+["']\.\/([^"']+\.css)["']/g)].map((match) => match[1]);
    expect(rootCssImports).toEqual(expected);
  });

  it("keeps headless-vendor imports behind components/ui", () => {
    const workspaceRoot = join(ROOT, "components", "workspace");
    const offenders = sourceFiles(workspaceRoot)
      .filter((path) => /@headlessui\/react|@radix-ui\//.test(readFileSync(path, "utf8")))
      .map((path) => relative(ROOT, path));

    expect(offenders).toEqual([]);
  });
});

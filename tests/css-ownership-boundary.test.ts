import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = process.cwd();
const APP = join(ROOT, "app");

function read(path: string): string {
  return readFileSync(join(ROOT, path), "utf8");
}

function filesMatching(root: string, pattern: RegExp): string[] {
  return readdirSync(root).flatMap((entry) => {
    const path = join(root, entry);
    if (statSync(path).isDirectory()) return filesMatching(path, pattern);
    return pattern.test(entry) ? [path] : [];
  });
}

function sourceFiles(root: string): string[] {
  return filesMatching(root, /\.(?:ts|tsx)$/);
}

function cssFiles(root: string): string[] {
  return filesMatching(root, /\.css$/);
}

const RAW_COLOR = /#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i;
const LEGACY_TOKEN = /var\(--(?:bg|bg-subtle|panel(?:-[234])?|text|muted|accent(?:-strong|-soft|-2|-soft-2)?|border(?:-strong)?|danger(?:-soft)?|success(?:-soft)?|r-(?:sm|md|lg|xl|full)|s-[1-8]|fs-(?:xs|sm|base|md|lg|xl|2xl)|fw-(?:normal|medium|semibold|bold)|ease|dur|shell-(?:sidebar|chat))\)/;
const LEGACY_RENDERER_TOKEN_NAME = /["']--(?:bg|bg-subtle|panel(?:-[234])?|text|muted|accent(?:-strong|-soft|-2|-soft-2)?|border(?:-strong)?)["']/;

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

  it("keeps globals.css document-only instead of growing a second component system", () => {
    const globals = read("app/globals.css");

    expect(globals).not.toMatch(/(^|\n)\s*\.[A-Za-z_-][\w-]*/m);
    expect(globals).not.toMatch(RAW_COLOR);
    expect(globals).not.toMatch(/(^|\n)\s*:root\s*\{/m);
    expect(globals).not.toMatch(/--(?:bg|panel|accent|muted|border|radius|space|type|shadow)-?[\w-]*\s*:/);
    expect(globals).not.toMatch(/\.(?:btn|button|card|chip|panel|dialog|menu|tooltip|transport|studio|piece|ask|library|inspector)[\w-]*/i);
  });

  it("keeps ordinary primitive color decisions on canonical tokens", () => {
    const uiRoot = join(ROOT, "components", "ui");
    const offenders = cssFiles(uiRoot)
      .filter((path) => RAW_COLOR.test(readFileSync(path, "utf8")))
      .map((path) => relative(ROOT, path));

    expect(offenders).toEqual([]);
  });

  it("does not use migration-era token aliases in shared primitives", () => {
    const uiRoot = join(ROOT, "components", "ui");
    const offenders = cssFiles(uiRoot)
      .filter((path) => LEGACY_TOKEN.test(readFileSync(path, "utf8")))
      .map((path) => relative(ROOT, path));

    expect(offenders).toEqual([]);
  });

  it("uses canonical token names in canvas renderer consumers", () => {
    const renderers = [
      "components/workspace/representations/Waveform.tsx",
      "components/workspace/representations/Spectrogram.tsx",
    ];

    for (const path of renderers) {
      const source = read(path);
      expect(source, path).not.toMatch(LEGACY_RENDERER_TOKEN_NAME);
      expect(source, path).not.toContain('className="muted');
    }
  });

  it("keeps headless-vendor imports behind components/ui", () => {
    const workspaceRoot = join(ROOT, "components", "workspace");
    const offenders = sourceFiles(workspaceRoot)
      .filter((path) => /@headlessui\/react|@radix-ui\//.test(readFileSync(path, "utf8")))
      .map((path) => relative(ROOT, path));

    expect(offenders).toEqual([]);
  });
});

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = process.cwd();
const COMPONENTS = join(ROOT, "components");
const UI = join(COMPONENTS, "ui");

function filesUnder(root: string): string[] {
  const result: string[] = [];
  for (const name of readdirSync(root)) {
    const path = join(root, name);
    if (statSync(path).isDirectory()) result.push(...filesUnder(path));
    else result.push(path);
  }
  return result;
}

function sourceFiles(root: string): string[] {
  return filesUnder(root).filter((path) => /\.(?:ts|tsx|css)$/.test(path));
}

function repoPath(path: string): string {
  return relative(ROOT, path).replaceAll("\\", "/");
}

describe("UI system ownership", () => {
  it("keeps headless vendor imports behind components/ui", () => {
    const vendorImport = /from\s+["'](?:@headlessui\/react|@radix-ui\/[^"']+)["']/;
    const offenders = sourceFiles(COMPONENTS)
      .filter((path) => !path.startsWith(`${UI}/`))
      .filter((path) => vendorImport.test(readFileSync(path, "utf8")))
      .map(repoPath);

    expect(offenders).toEqual([]);
  });

  it("keeps generic primitive names feature-neutral", () => {
    const featureCoupling = /(?:piece-source|library-|ask-|transport-|inspector-|workspace-)/;
    const offenders = sourceFiles(UI)
      .filter((path) => featureCoupling.test(readFileSync(path, "utf8")))
      .map(repoPath);

    expect(offenders).toEqual([]);
  });

  it("does not use transition-all behavior in generic primitives", () => {
    const offenders = sourceFiles(UI)
      .filter((path) => /transition\s*:\s*all\b/.test(readFileSync(path, "utf8")))
      .map(repoPath);

    expect(offenders).toEqual([]);
  });
});

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const APP = join(process.cwd(), "app");

function rootCustomProperties(path: string): string[] {
  const css = readFileSync(path, "utf8");
  const names: string[] = [];
  for (const match of css.matchAll(/:root\s*\{([\s\S]*?)\}/g)) {
    if (match.index === undefined) continue;
    const enclosingHeader =
      css.slice(0, match.index).split(/[{};]/).map((part) => part.trim()).filter(Boolean).at(-1) ?? "";
    if (enclosingHeader.startsWith("@media")) continue;
    names.push(...[...match[1].matchAll(/(^|\n)\s*(--[\w-]+)\s*:/g)].map((item) => item[2]));
  }
  return names;
}

describe("global CSS ownership", () => {
  it("keeps ordinary chrome tokens single-owned by app/tokens.css", () => {
    const canonical = new Set(rootCustomProperties(join(APP, "tokens.css")));

    const offenders = readdirSync(APP)
      .filter((entry) => entry.endsWith(".css") && entry !== "tokens.css")
      .flatMap((entry) =>
        rootCustomProperties(join(APP, entry))
          .filter((token) => canonical.has(token))
          .map((token) => `${entry}:${token}`),
      );

    expect(offenders).toEqual([]);
  });
});
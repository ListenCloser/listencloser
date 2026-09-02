import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

function rootCustomProperties(path: URL): string[] {
  const css = readFileSync(path, "utf8");
  const rootBlock = css.match(/:root\s*\{([\s\S]*?)\}/)?.[1];
  if (!rootBlock) return [];

  return [...rootBlock.matchAll(/(^|\n)\s*(--[\w-]+)\s*:/g)].map((match) => match[2]);
}

describe("global CSS ownership", () => {
  it("keeps workspace and product root tokens single-owned", () => {
    const workspaceTokens = new Set(
      rootCustomProperties(new URL("../app/workspace-v3.css", import.meta.url)),
    );
    const productTokens = rootCustomProperties(
      new URL("../app/product-polish-v4.css", import.meta.url),
    );

    const duplicateTokens = productTokens.filter((token) => workspaceTokens.has(token));

    expect(duplicateTokens).toEqual([]);
  });
});

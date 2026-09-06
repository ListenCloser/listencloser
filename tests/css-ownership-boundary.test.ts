import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = process.cwd();

describe("CSS ownership", () => {
  it("does not restore the retired custom source-picker selectors", () => {
    const interactions = readFileSync(join(ROOT, "app/workspace-interactions.css"), "utf8");

    expect(interactions).not.toMatch(/\.piece-source-(?:select|trigger|menu)\b/);
  });
});

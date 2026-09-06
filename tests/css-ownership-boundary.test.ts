import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

const repoRoot = path.resolve(import.meta.dirname, "..");

function read(relativePath: string): string {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("retired source-picker selectors do not return to global workspace CSS", () => {
  const interactions = read("app/workspace-interactions.css");

  assert.doesNotMatch(interactions, /\.piece-source-(?:select|trigger|menu)\b/);
});

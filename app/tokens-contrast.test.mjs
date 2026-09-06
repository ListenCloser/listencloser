import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

function token(name) {
  const css = readFileSync(new URL("./tokens.css", import.meta.url), "utf8");
  const match = css.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!match) throw new Error(`missing hex token --${name}`);
  return match[1];
}

function relativeLuminance(hex) {
  const channels = [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255);
  const linear = channels.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(foreground, background) {
  const lighter = Math.max(relativeLuminance(foreground), relativeLuminance(background));
  const darker = Math.min(relativeLuminance(foreground), relativeLuminance(background));
  return (lighter + 0.05) / (darker + 0.05);
}

describe("canonical tertiary text contrast", () => {
  it("clears WCAG AA on the dark workspace surfaces observed by axe", () => {
    const tertiary = token("text-tertiary");
    const observedBackgrounds = ["#111411", "#151815", "#1b1b17", "#1e2118"];

    for (const background of observedBackgrounds) {
      expect(contrastRatio(tertiary, background)).toBeGreaterThanOrEqual(4.5);
    }
  });
});

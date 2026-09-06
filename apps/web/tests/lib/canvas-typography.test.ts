import { describe, expect, it } from "vitest";
import { canvasMeasurementFont } from "@/lib/canvas-typography";

function styles(values: Record<string, string>): CSSStyleDeclaration {
  return {
    getPropertyValue: (name: string) => values[name] ?? "",
  } as CSSStyleDeclaration;
}

describe("canvasMeasurementFont", () => {
  it("uses the shared measurement size, weight, and UI family tokens", () => {
    expect(canvasMeasurementFont(styles({
      "--measurement-font-size": "10px",
      "--measurement-font-weight": "500",
      "--font-sans": 'Inter, "Segoe UI", sans-serif',
    }))).toBe('500 10px Inter, "Segoe UI", sans-serif');
  });

  it("falls back to the shared measurement contract instead of monospace", () => {
    const font = canvasMeasurementFont(styles({}));
    expect(font).toBe("500 10px system-ui, sans-serif");
    expect(font).not.toContain("monospace");
  });
});

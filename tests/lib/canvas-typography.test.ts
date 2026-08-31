import { describe, expect, it } from "vitest";
import { canvasMeasurementFont } from "@/lib/canvas-typography";

function styles(values: Record<string, string>): CSSStyleDeclaration {
  return {
    getPropertyValue: (name: string) => values[name] ?? "",
  } as CSSStyleDeclaration;
}

describe("canvasMeasurementFont", () => {
  it("uses the same sans-serif family and xs size tokens as the application UI", () => {
    expect(canvasMeasurementFont(styles({
      "--fs-xs": "12px",
      "--font-sans": 'Inter, "Segoe UI", sans-serif',
    }))).toBe('12px Inter, "Segoe UI", sans-serif');
  });

  it("falls back to a UI font instead of monospace when CSS tokens are unavailable", () => {
    const font = canvasMeasurementFont(styles({}));
    expect(font).toBe("11px system-ui, sans-serif");
    expect(font).not.toContain("monospace");
  });
});

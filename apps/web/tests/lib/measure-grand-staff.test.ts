import { describe, expect, it, vi } from "vitest";
import { measureGroupsForIndex } from "@/lib/measure";
import { unionMeasureStructuralBoxes } from "@/lib/score-measure-geometry";

function makeSvgWithGrandStaff(): SVGSVGElement {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");

  // Treble staff, measure 1
  const g1a = document.createElementNS(NS, "g");
  g1a.classList.add("vf-measure");
  g1a.setAttribute("id", "1");
  svg.appendChild(g1a);

  // Bass staff, measure 1
  const g1b = document.createElementNS(NS, "g");
  g1b.classList.add("vf-measure");
  g1b.setAttribute("id", "1");
  svg.appendChild(g1b);

  // Treble staff, measure 2
  const g2a = document.createElementNS(NS, "g");
  g2a.classList.add("vf-measure");
  g2a.setAttribute("id", "2");
  svg.appendChild(g2a);

  // Bass staff, measure 2
  const g2b = document.createElementNS(NS, "g");
  g2b.classList.add("vf-measure");
  g2b.setAttribute("id", "2");
  svg.appendChild(g2b);

  return svg;
}

function appendStave(
  group: SVGGraphicsElement,
  box: { x: number; y: number; width: number; height: number },
): SVGGraphicsElement {
  const NS = "http://www.w3.org/2000/svg";
  const stave = document.createElementNS(NS, "g");
  stave.classList.add("vf-stave");
  stave.getBBox = vi.fn(() => box as DOMRect);
  group.appendChild(stave);
  return stave;
}

describe("measureGroupsForIndex (grand-staff)", () => {
  it("returns two groups for a logical measure on grand-staff", () => {
    const svg = makeSvgWithGrandStaff();
    const groups0 = measureGroupsForIndex(svg, 0);
    const groups1 = measureGroupsForIndex(svg, 1);
    expect(groups0).toHaveLength(2);
    expect(groups1).toHaveLength(2);
  });

  it("returns groups with the correct 1-based id", () => {
    const svg = makeSvgWithGrandStaff();
    const groups0 = measureGroupsForIndex(svg, 0);
    for (const g of groups0) {
      expect(g.getAttribute("id")).toBe("1");
    }
    const groups1 = measureGroupsForIndex(svg, 1);
    for (const g of groups1) {
      expect(g.getAttribute("id")).toBe("2");
    }
  });

  it("returns empty array for out-of-range measure", () => {
    const svg = makeSvgWithGrandStaff();
    expect(measureGroupsForIndex(svg, 5)).toHaveLength(0);
  });
});

describe("logical grand-staff measure geometry", () => {
  it("unions treble and bass groups into one logical measure box", () => {
    const svg = makeSvgWithGrandStaff();
    const groups = measureGroupsForIndex(svg, 0);

    groups[0].getBBox = vi.fn(() => ({ x: 10, y: 20, width: 100, height: 30 }) as DOMRect);
    groups[1].getBBox = vi.fn(() => ({ x: 10, y: 60, width: 100, height: 30 }) as DOMRect);

    expect(unionMeasureStructuralBoxes(groups)).toEqual({
      x: 10,
      y: 20,
      width: 100,
      height: 70,
    });
  });

  it("ignores zero-area groups rather than creating duplicate or degenerate overlay geometry", () => {
    const svg = makeSvgWithGrandStaff();
    const groups = measureGroupsForIndex(svg, 0);

    groups[0].getBBox = vi.fn(() => ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect);
    groups[1].getBBox = vi.fn(() => ({ x: 10, y: 60, width: 100, height: 30 }) as DOMRect);

    expect(unionMeasureStructuralBoxes(groups)).toEqual({
      x: 10,
      y: 60,
      width: 100,
      height: 30,
    });
  });

  it("uses stave geometry instead of tie/slur-inflated measure descendants", () => {
    const svg = makeSvgWithGrandStaff();
    const groups = measureGroupsForIndex(svg, 0);

    appendStave(groups[0], { x: 12, y: 20, width: 96, height: 50 });
    appendStave(groups[1], { x: 12, y: 90, width: 96, height: 50 });

    // Simulate ties/slurs/lyrics expanding each enclosing measure bbox. The
    // logical overlay must remain based on the stave footprints above.
    groups[0].getBBox = vi.fn(() => ({ x: 0, y: 0, width: 150, height: 100 }) as DOMRect);
    groups[1].getBBox = vi.fn(() => ({ x: 0, y: 70, width: 150, height: 100 }) as DOMRect);

    expect(unionMeasureStructuralBoxes(groups)).toEqual({
      x: 12,
      y: 17,
      width: 96,
      height: 126,
    });
  });
});

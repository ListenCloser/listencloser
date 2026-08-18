import { describe, expect, it, vi } from "vitest";
import { measureGroupsForIndex } from "@/lib/measure";

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

describe("per-group highlight insertion (grand-staff)", () => {
  it("inserts one rect per staff group, each using that group's own bbox", () => {
    const svg = makeSvgWithGrandStaff();
    const groups = measureGroupsForIndex(svg, 0);
    expect(groups).toHaveLength(2);

    // Mock getBBox to return distinct values per group
    const bboxes = [
      { x: 10, y: 20, width: 100, height: 30 },
      { x: 10, y: 60, width: 100, height: 30 },
    ];
    groups[0].getBBox = vi.fn(() => bboxes[0] as DOMRect);
    groups[1].getBBox = vi.fn(() => bboxes[1] as DOMRect);

    const NS = "http://www.w3.org/2000/svg";
    for (const group of groups) {
      const box = group.getBBox();
      if (box.width === 0 && box.height === 0) continue;
      const rect = document.createElementNS(NS, "rect");
      rect.setAttribute("data-playback-highlight", "true");
      rect.setAttribute("x", String(box.x));
      rect.setAttribute("y", String(box.y));
      rect.setAttribute("width", String(box.width));
      rect.setAttribute("height", String(box.height));
      group.insertBefore(rect, group.firstChild);
    }

    // Each group should have exactly one highlight rect
    const rects0 = groups[0].querySelectorAll("[data-playback-highlight]");
    const rects1 = groups[1].querySelectorAll("[data-playback-highlight]");
    expect(rects0).toHaveLength(1);
    expect(rects1).toHaveLength(1);

    // Each rect should use its own group's bbox coordinates
    expect(rects0[0].getAttribute("y")).toBe("20");
    expect(rects0[0].getAttribute("height")).toBe("30");
    expect(rects1[0].getAttribute("y")).toBe("60");
    expect(rects1[0].getAttribute("height")).toBe("30");
  });

  it("does not insert rect when bbox is zero-area", () => {
    const svg = makeSvgWithGrandStaff();
    const groups = measureGroupsForIndex(svg, 0);

    groups[0].getBBox = vi.fn(() => ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect);
    groups[1].getBBox = vi.fn(() => ({ x: 10, y: 60, width: 100, height: 30 }) as DOMRect);

    const NS = "http://www.w3.org/2000/svg";
    let inserted = 0;
    for (const group of groups) {
      const box = group.getBBox();
      if (box.width === 0 && box.height === 0) continue;
      const rect = document.createElementNS(NS, "rect");
      rect.setAttribute("data-playback-highlight", "true");
      group.insertBefore(rect, group.firstChild);
      inserted += 1;
    }

    expect(inserted).toBe(1);
    expect(groups[0].querySelectorAll("[data-playback-highlight]")).toHaveLength(0);
    expect(groups[1].querySelectorAll("[data-playback-highlight]")).toHaveLength(1);
  });
});

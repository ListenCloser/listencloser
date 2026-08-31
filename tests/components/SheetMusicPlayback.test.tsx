import { render, screen } from "@testing-library/react";
import SheetMusic, {
  insertHighlightRect,
  insertLogicalHighlightRect,
} from "@/components/SheetMusic";

type Box = { x: number; y: number; width: number; height: number };

function makeGroup(getBBox: () => Box): SVGGElement {
  const ns = "http://www.w3.org/2000/svg";
  const g = document.createElementNS(ns, "g");
  g.classList.add("vf-measure");
  (g as any).getBBox = getBBox;
  return g;
}

function makeStructuralGroup(measureBox: Box, staveBox: Box): SVGGElement {
  const ns = "http://www.w3.org/2000/svg";
  const group = makeGroup(() => measureBox);
  const stave = document.createElementNS(ns, "g");
  stave.classList.add("vf-stave");
  (stave as any).getBBox = () => staveBox;
  group.appendChild(stave);
  return group;
}

describe("insertHighlightRect", () => {
  it("returns false and inserts nothing when getBBox is zero-size", () => {
    const g = makeGroup(() => ({ x: 0, y: 0, width: 0, height: 0 }));
    const ok = insertHighlightRect(g, "data-playback-highlight", "red", "0.5", "red", "2", "none");
    expect(ok).toBe(false);
    expect(g.querySelector("[data-playback-highlight]")).toBeNull();
  });

  it("insets a valid measure overlay inside the OSMD bounds", () => {
    const g = makeGroup(() => ({ x: 10, y: 20, width: 150, height: 100 }));
    const ok = insertHighlightRect(g, "data-playback-highlight", "blue", "0.3", "blue", "1", "none");
    expect(ok).toBe(true);
    const rect = g.querySelector("[data-playback-highlight]");
    expect(rect).not.toBeNull();
    expect(rect!.getAttribute("x")).toBe("11.5");
    expect(rect!.getAttribute("y")).toBe("20.75");
    expect(rect!.getAttribute("width")).toBe("147");
    expect(rect!.getAttribute("height")).toBe("98.5");
  });

  it("does not insert duplicate rects on repeated calls", () => {
    const g = makeGroup(() => ({ x: 10, y: 20, width: 150, height: 100 }));
    insertHighlightRect(g, "data-playback-highlight", "red", "0.5", "red", "2", "none");
    insertHighlightRect(g, "data-playback-highlight", "red", "0.5", "red", "2", "none");
    expect(g.querySelectorAll("[data-playback-highlight]").length).toBe(1);
  });

  it("inserts an inset rect after getBBox transitions from zero to valid", () => {
    let callCount = 0;
    const g = makeGroup(() => {
      callCount += 1;
      if (callCount <= 1) return { x: 0, y: 0, width: 0, height: 0 };
      return { x: 5, y: 10, width: 200, height: 60 };
    });

    const ok1 = insertHighlightRect(g, "data-playback-highlight", "green", "0.2", "green", "1", "none");
    expect(ok1).toBe(false);
    expect(g.querySelector("[data-playback-highlight]")).toBeNull();

    const ok2 = insertHighlightRect(g, "data-playback-highlight", "green", "0.2", "green", "1", "none");
    expect(ok2).toBe(true);
    const rect = g.querySelector("[data-playback-highlight]");
    expect(rect).not.toBeNull();
    expect(rect!.getAttribute("x")).toBe("6.5");
    expect(rect!.getAttribute("width")).toBe("197");
  });

  it("inserts independent rects for different dataAttr values", () => {
    const g = makeGroup(() => ({ x: 10, y: 20, width: 100, height: 50 }));
    insertHighlightRect(g, "data-playback-highlight", "red", "0.5", "red", "2", "none");
    insertHighlightRect(g, "data-selection-highlight", "blue", "0.3", "blue", "1", "4 3");
    expect(g.querySelectorAll("[data-playback-highlight]").length).toBe(1);
    expect(g.querySelectorAll("[data-selection-highlight]").length).toBe(1);
  });
});

describe("insertLogicalHighlightRect", () => {
  it("uses one structural overlay for treble and bass groups of the same measure", () => {
    const treble = makeStructuralGroup(
      { x: 0, y: 0, width: 220, height: 180 },
      { x: 10, y: 20, width: 100, height: 30 },
    );
    const bass = makeStructuralGroup(
      { x: -20, y: -30, width: 260, height: 230 },
      { x: 10, y: 70, width: 100, height: 30 },
    );

    const ok = insertLogicalHighlightRect(
      [treble, bass],
      "data-selection-highlight",
      "blue",
      "0.1",
      "blue",
      "1",
      "none",
    );

    expect(ok).toBe(true);
    expect(treble.querySelectorAll("[data-selection-highlight]")).toHaveLength(1);
    expect(bass.querySelectorAll("[data-selection-highlight]")).toHaveLength(0);

    const rect = treble.querySelector<SVGRectElement>("[data-selection-highlight]");
    expect(rect).not.toBeNull();
    expect(Number(rect!.getAttribute("x"))).toBeCloseTo(11.5);
    expect(Number(rect!.getAttribute("y"))).toBeCloseTo(18.95);
    expect(Number(rect!.getAttribute("width"))).toBeCloseTo(97);
    expect(Number(rect!.getAttribute("height"))).toBeCloseTo(82.1);
  });

  it("does not duplicate a logical overlay when the same measure is updated again", () => {
    const treble = makeStructuralGroup(
      { x: 0, y: 0, width: 200, height: 100 },
      { x: 10, y: 20, width: 80, height: 30 },
    );
    const bass = makeStructuralGroup(
      { x: 0, y: 0, width: 200, height: 100 },
      { x: 10, y: 60, width: 80, height: 30 },
    );

    insertLogicalHighlightRect([treble, bass], "data-annotation-highlight", "red", "0.1", "red", "1", "none");
    insertLogicalHighlightRect([treble, bass], "data-annotation-highlight", "red", "0.2", "red", "2", "none");

    expect(treble.querySelectorAll("[data-annotation-highlight]")).toHaveLength(1);
    expect(bass.querySelectorAll("[data-annotation-highlight]")).toHaveLength(0);
  });
});

describe("SheetMusic", () => {
  it("renders a concise fallback when musicXml is empty", () => {
    render(<SheetMusic musicXml="" />);
    expect(screen.getByText("Score unavailable.")).toBeInTheDocument();
  });
});

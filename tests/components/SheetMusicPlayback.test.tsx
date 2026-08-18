import { render, screen } from "@testing-library/react";
import SheetMusic, { insertHighlightRect } from "@/components/SheetMusic";

const minimalMusicXml = `<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1"><attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note></measure>
    <measure number="2"><note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note></measure>
  </part>
</score-partwise>`;

function makeGroup(
  getBBox: () => { x: number; y: number; width: number; height: number },
): SVGGElement {
  const ns = "http://www.w3.org/2000/svg";
  const g = document.createElementNS(ns, "g");
  g.classList.add("vf-measure");
  (g as any).getBBox = getBBox;
  return g;
}

describe("insertHighlightRect", () => {
  it("returns false and inserts nothing when getBBox is zero-size", () => {
    const g = makeGroup(() => ({ x: 0, y: 0, width: 0, height: 0 }));
    const ok = insertHighlightRect(g, "data-playback-highlight", "red", "0.5", "red", "2", "none");
    expect(ok).toBe(false);
    expect(g.querySelector("[data-playback-highlight]")).toBeNull();
  });

  it("returns true and inserts a rect when getBBox has valid size", () => {
    const g = makeGroup(() => ({ x: 10, y: 20, width: 150, height: 100 }));
    const ok = insertHighlightRect(g, "data-playback-highlight", "blue", "0.3", "blue", "1", "none");
    expect(ok).toBe(true);
    const rect = g.querySelector("[data-playback-highlight]");
    expect(rect).not.toBeNull();
    expect(rect!.getAttribute("x")).toBe("10");
    expect(rect!.getAttribute("y")).toBe("20");
    expect(rect!.getAttribute("width")).toBe("150");
    expect(rect!.getAttribute("height")).toBe("100");
  });

  it("does not insert duplicate rects on repeated calls", () => {
    const g = makeGroup(() => ({ x: 10, y: 20, width: 150, height: 100 }));
    insertHighlightRect(g, "data-playback-highlight", "red", "0.5", "red", "2", "none");
    insertHighlightRect(g, "data-playback-highlight", "red", "0.5", "red", "2", "none");
    expect(g.querySelectorAll("[data-playback-highlight]").length).toBe(1);
  });

  it("inserts rect after getBBox transitions from zero to valid (retry scenario)", () => {
    let callCount = 0;
    const g = makeGroup(() => {
      callCount += 1;
      if (callCount <= 1) return { x: 0, y: 0, width: 0, height: 0 };
      return { x: 5, y: 10, width: 200, height: 60 };
    });

    // First call: zero-size → fails.
    const ok1 = insertHighlightRect(g, "data-playback-highlight", "green", "0.2", "green", "1", "none");
    expect(ok1).toBe(false);
    expect(g.querySelector("[data-playback-highlight]")).toBeNull();

    // Second call (retry): valid size → succeeds.
    const ok2 = insertHighlightRect(g, "data-playback-highlight", "green", "0.2", "green", "1", "none");
    expect(ok2).toBe(true);
    const rect = g.querySelector("[data-playback-highlight]");
    expect(rect).not.toBeNull();
    expect(rect!.getAttribute("x")).toBe("5");
    expect(rect!.getAttribute("width")).toBe("200");
  });

  it("inserts independent rects for different dataAttr values", () => {
    const g = makeGroup(() => ({ x: 10, y: 20, width: 100, height: 50 }));
    insertHighlightRect(g, "data-playback-highlight", "red", "0.5", "red", "2", "none");
    insertHighlightRect(g, "data-selection-highlight", "blue", "0.3", "blue", "1", "4 3");
    expect(g.querySelectorAll("[data-playback-highlight]").length).toBe(1);
    expect(g.querySelectorAll("[data-selection-highlight]").length).toBe(1);
  });
});

describe("SheetMusic", () => {
  it("renders fallback when musicXml is empty", () => {
    render(<SheetMusic musicXml="" />);
    expect(screen.getByText("No sheet music data available.")).toBeInTheDocument();
  });
});

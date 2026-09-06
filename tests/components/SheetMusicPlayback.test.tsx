import { render, screen } from "@testing-library/react";
import SheetMusic, { insertHighlightRect } from "@/components/workspace/representations/SheetMusic";
import {
  SCORE_PLAYBACK_ACTIVE_ATTR,
  activeScoreNoteheadsAt,
  buildScoreNotePlaybackEvents,
  clearScoreActiveNoteheads,
  syncScoreActiveNoteheads,
} from "@/lib/score-note-playback";

function makeGroup(
  getBBox: () => { x: number; y: number; width: number; height: number },
): SVGGElement {
  const ns = "http://www.w3.org/2000/svg";
  const g = document.createElementNS(ns, "g");
  g.classList.add("vf-measure");
  (g as any).getBBox = getBBox;
  return g;
}

function makeNotehead() {
  return document.createElementNS("http://www.w3.org/2000/svg", "path");
}

function makeGraphicalNote(notehead: Element, length = 0.25) {
  return {
    sourceNote: {
      Length: { RealValue: length },
      Pitch: {},
      isRest: () => false,
    },
    getNoteheadSVGs: () => [notehead],
  };
}

function makeGraphicalMeasure(relativeStart: number, notes: ReturnType<typeof makeGraphicalNote>[], duration = 1) {
  return {
    parentSourceMeasure: { Duration: { RealValue: duration } },
    staffEntries: [{
      relInMeasureTimestamp: { RealValue: relativeStart },
      graphicalVoiceEntries: [{ notes }],
    }],
  };
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

describe("score note playback mapping", () => {
  it("maps a simultaneous grand-staff chord to the same notation-time instant", () => {
    const trebleRoot = makeNotehead();
    const trebleThird = makeNotehead();
    const bassRoot = makeNotehead();
    const osmd = {
      GraphicSheet: {
        MeasureList: [[
          makeGraphicalMeasure(0.5, [makeGraphicalNote(trebleRoot), makeGraphicalNote(trebleThird)]),
          makeGraphicalMeasure(0.5, [makeGraphicalNote(bassRoot)]),
        ]],
      },
    };

    const events = buildScoreNotePlaybackEvents(osmd, [0], 4);
    expect(events).toHaveLength(3);
    expect(events.every((event) => event.startSeconds === 2 && event.endSeconds === 3)).toBe(true);

    const active = activeScoreNoteheadsAt(events, 2.5);
    expect(active).toEqual(new Set([trebleRoot, trebleThird, bassRoot]));
  });

  it("switches the active notehead set on seek and clears stale state", () => {
    const first = makeNotehead();
    const second = makeNotehead();
    const osmd = {
      GraphicSheet: {
        MeasureList: [[
          makeGraphicalMeasure(0, [makeGraphicalNote(first)]),
          makeGraphicalMeasure(0.5, [makeGraphicalNote(second)]),
        ]],
      },
    };
    const events = buildScoreNotePlaybackEvents(osmd, [0], 4);

    let active = syncScoreActiveNoteheads(events, 0.5, new Set());
    expect(first.getAttribute(SCORE_PLAYBACK_ACTIVE_ATTR)).toBe("true");
    expect(second.hasAttribute(SCORE_PLAYBACK_ACTIVE_ATTR)).toBe(false);

    active = syncScoreActiveNoteheads(events, 2.5, active);
    expect(first.hasAttribute(SCORE_PLAYBACK_ACTIVE_ATTR)).toBe(false);
    expect(second.getAttribute(SCORE_PLAYBACK_ACTIVE_ATTR)).toBe("true");

    clearScoreActiveNoteheads(active);
    expect(second.hasAttribute(SCORE_PLAYBACK_ACTIVE_ATTR)).toBe(false);
    expect(active.size).toBe(0);
  });

  it("uses each measure's persisted notation-time span instead of assuming a BPM", () => {
    const firstMeasureNote = makeNotehead();
    const secondMeasureNote = makeNotehead();
    const osmd = {
      GraphicSheet: {
        MeasureList: [
          [makeGraphicalMeasure(0.5, [makeGraphicalNote(firstMeasureNote, 0.25)])],
          [makeGraphicalMeasure(0.25, [makeGraphicalNote(secondMeasureNote, 0.5)])],
        ],
      },
    };

    const events = buildScoreNotePlaybackEvents(osmd, [0, 3], 9);
    expect(events[0]).toMatchObject({ startSeconds: 1.5, endSeconds: 2.25 });
    expect(events[1]).toMatchObject({ startSeconds: 4.5, endSeconds: 7.5 });
  });
});

describe("SheetMusic", () => {
  it("renders a concise fallback when musicXml is empty", () => {
    render(<SheetMusic musicXml="" />);
    expect(screen.getByText("Score unavailable.")).toBeInTheDocument();
  });
});

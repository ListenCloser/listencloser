import { describe, expect, it } from "vitest";
import {
  measureInteractionClientRect,
  measureStructuralBox,
  measureStructuralClientRect,
  unionMeasureClientRects,
} from "@/lib/score-measure-geometry";

type Box = { x: number; y: number; width: number; height: number };
type ClientRect = { left: number; right: number; top: number; bottom: number; width?: number; height?: number };

function fakeGraphic(box: Box, client: ClientRect): SVGGraphicsElement {
  return {
    getBBox: () => box,
    getBoundingClientRect: () => ({
      ...client,
      x: client.left,
      y: client.top,
      width: client.width ?? client.right - client.left,
      height: client.height ?? client.bottom - client.top,
      toJSON: () => ({}),
    }),
  } as unknown as SVGGraphicsElement;
}

function fakeMeasure(
  measureBox: Box,
  measureClient: ClientRect,
  staves: SVGGraphicsElement[],
): SVGGraphicsElement {
  return {
    getBBox: () => measureBox,
    getBoundingClientRect: () => ({
      ...measureClient,
      x: measureClient.left,
      y: measureClient.top,
      width: measureClient.width ?? measureClient.right - measureClient.left,
      height: measureClient.height ?? measureClient.bottom - measureClient.top,
      toJSON: () => ({}),
    }),
    querySelectorAll: (selector: string) => selector === "g.vf-stave" ? staves : [],
  } as unknown as SVGGraphicsElement;
}

describe("score measure structural geometry", () => {
  it("uses grand-staff groups instead of a tie-expanded measure bbox", () => {
    const treble = fakeGraphic(
      { x: 12, y: 30, width: 108, height: 32 },
      { left: 112, right: 220, top: 230, bottom: 262 },
    );
    const bass = fakeGraphic(
      { x: 12, y: 82, width: 108, height: 32 },
      { left: 112, right: 220, top: 282, bottom: 314 },
    );
    const measure = fakeMeasure(
      // Simulates a slur/tie extending well above/below and to the right.
      { x: 4, y: 5, width: 150, height: 145 },
      { left: 104, right: 254, top: 180, bottom: 380 },
      [treble, bass],
    );

    expect(measureStructuralBox(measure)).toEqual({
      x: 12,
      y: 27,
      width: 108,
      height: 90,
    });
    expect(measureStructuralClientRect(measure)).toEqual({
      left: 112,
      right: 220,
      top: 226,
      bottom: 318,
    });
  });

  it("keeps hit-testing horizontally structural while allowing bounded ledger-note reach", () => {
    const treble = fakeGraphic(
      { x: 12, y: 30, width: 108, height: 32 },
      { left: 112, right: 220, top: 230, bottom: 262 },
    );
    const bass = fakeGraphic(
      { x: 12, y: 82, width: 108, height: 32 },
      { left: 112, right: 220, top: 282, bottom: 314 },
    );
    const measure = fakeMeasure(
      { x: 4, y: 5, width: 150, height: 145 },
      // Descendants extend far beyond the staves in both axes. The interaction
      // rect admits nearby ledger-note space but does not inherit all overflow.
      { left: 80, right: 280, top: 150, bottom: 390 },
      [treble, bass],
    );

    expect(measureInteractionClientRect(measure)).toEqual({
      left: 112,
      right: 220,
      top: 198,
      bottom: 346,
    });
  });

  it("falls back to the measure box when stave groups are unavailable", () => {
    const measure = fakeMeasure(
      { x: 10, y: 20, width: 80, height: 40 },
      { left: 110, right: 190, top: 220, bottom: 260 },
      [],
    );

    expect(measureStructuralBox(measure)).toEqual({ x: 10, y: 20, width: 80, height: 40 });
    expect(measureStructuralClientRect(measure)).toEqual({ left: 110, right: 190, top: 220, bottom: 260 });
    expect(measureInteractionClientRect(measure)).toEqual({ left: 110, right: 190, top: 220, bottom: 260 });
  });

  it("unions multiple measure footprints without inheriting descendant overflow", () => {
    const first = fakeMeasure(
      { x: 0, y: 0, width: 200, height: 100 },
      { left: 100, right: 300, top: 100, bottom: 200 },
      [fakeGraphic({ x: 10, y: 20, width: 80, height: 30 }, { left: 110, right: 190, top: 120, bottom: 150 })],
    );
    const second = fakeMeasure(
      { x: 0, y: 0, width: 220, height: 110 },
      { left: 300, right: 520, top: 90, bottom: 200 },
      [fakeGraphic({ x: 12, y: 18, width: 88, height: 30 }, { left: 312, right: 400, top: 118, bottom: 148 })],
    );

    expect(unionMeasureClientRects([first, second])).toEqual({
      left: 110,
      right: 400,
      top: 116.2,
      bottom: 151.8,
    });
  });
});

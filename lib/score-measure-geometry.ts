export type MeasureBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type MeasureClientRect = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

const MAX_INTERACTION_VERTICAL_EXTENSION_PX = 28;

function validBox(box: MeasureBox | null | undefined): box is MeasureBox {
  return Boolean(box && Number.isFinite(box.x) && Number.isFinite(box.y) && box.width > 0 && box.height >= 0);
}

function unionBoxes(boxes: MeasureBox[]): MeasureBox | null {
  const usable = boxes.filter(validBox);
  if (usable.length === 0) return null;
  const x = Math.min(...usable.map((box) => box.x));
  const y = Math.min(...usable.map((box) => box.y));
  const right = Math.max(...usable.map((box) => box.x + box.width));
  const bottom = Math.max(...usable.map((box) => box.y + box.height));
  return { x, y, width: right - x, height: bottom - y };
}

function unionClientRects(rects: MeasureClientRect[]): MeasureClientRect | null {
  const usable = rects.filter(
    (rect) => Number.isFinite(rect.left) && Number.isFinite(rect.right) && rect.right > rect.left && Number.isFinite(rect.top) && Number.isFinite(rect.bottom),
  );
  if (usable.length === 0) return null;
  return {
    left: Math.min(...usable.map((rect) => rect.left)),
    right: Math.max(...usable.map((rect) => rect.right)),
    top: Math.min(...usable.map((rect) => rect.top)),
    bottom: Math.max(...usable.map((rect) => rect.bottom)),
  };
}

function staveGroups(group: SVGGraphicsElement): SVGGraphicsElement[] {
  return Array.from(group.querySelectorAll<SVGGraphicsElement>("g.vf-stave"));
}

/**
 * Return the structural score footprint for a rendered VexFlow measure.
 *
 * VexFlow draws the horizontal staff lines inside dedicated `vf-stave` SVG
 * groups, then closes those groups before drawing modifiers. Ties, slurs,
 * noteheads, lyrics, and other descendants can therefore expand the enclosing
 * `vf-measure` bbox without changing the actual measure boundaries. Prefer the
 * stave groups and fall back to the whole measure only for renderers that do
 * not expose them.
 */
export function measureStructuralBox(group: SVGGraphicsElement): MeasureBox | null {
  const staveBoxes = staveGroups(group)
    .map((stave) => {
      try {
        const box = stave.getBBox();
        return { x: box.x, y: box.y, width: box.width, height: box.height };
      } catch {
        return null;
      }
    })
    .filter(validBox);

  const structural = unionBoxes(staveBoxes);
  if (structural) {
    const padY = Math.min(3, Math.max(1, structural.height * 0.06));
    return {
      x: structural.x,
      y: structural.y - padY,
      width: structural.width,
      height: structural.height + padY * 2,
    };
  }

  try {
    const fallback = group.getBBox();
    return validBox(fallback) ? fallback : null;
  } catch {
    return null;
  }
}

/** Client-space equivalent used by visual geometry, scrolling, and playback. */
export function measureStructuralClientRect(group: SVGGraphicsElement): MeasureClientRect | null {
  const staveRects = staveGroups(group)
    .map((stave) => {
      try {
        const rect = stave.getBoundingClientRect();
        return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
      } catch {
        return null;
      }
    })
    .filter((rect): rect is MeasureClientRect => rect !== null);

  const structural = unionClientRects(staveRects);
  if (structural) {
    const height = Math.max(0, structural.bottom - structural.top);
    const padY = Math.min(4, Math.max(1, height * 0.06));
    return {
      left: structural.left,
      right: structural.right,
      top: structural.top - padY,
      bottom: structural.bottom + padY,
    };
  }

  try {
    const rect = group.getBoundingClientRect();
    if (rect.width <= 0) return null;
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
  } catch {
    return null;
  }
}

/**
 * Hit-testing keeps structural horizontal bounds, but allows a bounded vertical
 * extension toward rendered descendants so high/low ledger notes remain easy
 * to click. This deliberately does not inherit arbitrary tie/slur overflow.
 */
export function measureInteractionClientRect(group: SVGGraphicsElement): MeasureClientRect | null {
  const structural = measureStructuralClientRect(group);
  if (!structural) return null;

  try {
    const rendered = group.getBoundingClientRect();
    const top = Number.isFinite(rendered.top)
      ? Math.max(rendered.top, structural.top - MAX_INTERACTION_VERTICAL_EXTENSION_PX)
      : structural.top;
    const bottom = Number.isFinite(rendered.bottom)
      ? Math.min(rendered.bottom, structural.bottom + MAX_INTERACTION_VERTICAL_EXTENSION_PX)
      : structural.bottom;
    return {
      left: structural.left,
      right: structural.right,
      top: Math.min(top, structural.top),
      bottom: Math.max(bottom, structural.bottom),
    };
  } catch {
    return structural;
  }
}

export function unionMeasureClientRects(groups: SVGGraphicsElement[]): MeasureClientRect | null {
  return unionClientRects(
    groups
      .map(measureStructuralClientRect)
      .filter((rect): rect is MeasureClientRect => rect !== null),
  );
}

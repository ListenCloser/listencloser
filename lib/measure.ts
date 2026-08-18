/**
 * Returns the 0-based index of the measure active at the given time.
 *
 *   []                          → -1
 *   time < starts[0]            → -1
 *   starts[i] <= time < starts[i+1] → i
 *   time >= starts[last]        → last index
 */
export function measureIndexAt(starts: number[], time: number): number {
  if (starts.length === 0) return -1;
  if (time < starts[0]) return -1;
  let index = 0;
  for (let i = 0; i < starts.length; i += 1) {
    if (starts[i] <= time) index = i;
    else break;
  }
  return index;
}

/**
 * Returns all SVG <g class="vf-measure"> elements that belong to the given
 * logical measure index.  OSMD/VexFlow renders one <g> per staff per measure,
 * each with the same `id` equal to the 1-based measure number.  For a
 * grand-staff piano score there are typically two groups per logical measure.
 */
export function measureGroupsForIndex(
  container: Element,
  measureIndex: number,
): SVGGraphicsElement[] {
  const oneBased = String(measureIndex + 1);
  return Array.from(
    container.querySelectorAll<SVGGraphicsElement>("g.vf-measure"),
  ).filter((el) => el.getAttribute("id") === oneBased);
}
